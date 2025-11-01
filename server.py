"""
HTTP RPC Server for Raft nodes.

Provides REST API for inter-node communication and client requests.
"""

import asyncio
import logging
from typing import Dict

from aiohttp import web, ClientSession, ClientTimeout
from raft import (
    RaftNode,
    RequestVoteRequest,
    AppendEntriesRequest,
)

logger = logging.getLogger(__name__)


class RaftServer:
    """HTTP server for a Raft node."""
    
    def __init__(self, raft_node: RaftNode):
        self.node = raft_node
        self.app = web.Application()
        self._setup_routes()
        self.runner = None
        self.client_session: ClientSession = None
        
        # Map peer IDs to their URLs
        self._update_peer_urls()
    
    def _update_peer_urls(self):
        """Update peer connection URLs."""
        # In this implementation, we assume peers are on sequential ports
        base_port = self.node.port
        node_index = self.node.all_nodes.index(self.node.node_id)
        
        for i, peer_id in enumerate(self.node.all_nodes):
            if peer_id != self.node.node_id:
                peer_index = self.node.all_nodes.index(peer_id)
                port = base_port - node_index + peer_index
                self.node.peer_connections[peer_id] = f"http://{self.node.host}:{port}"
    
    def _setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_post('/raft/request_vote', self.handle_request_vote)
        self.app.router.add_post('/raft/append_entries', self.handle_append_entries)
        self.app.router.add_post('/client/request', self.handle_client_request)
        self.app.router.add_get('/status', self.handle_status)
        self.app.router.add_get('/health', self.handle_health)
    
    async def handle_request_vote(self, request: web.Request) -> web.Response:
        """Handle RequestVote RPC."""
        try:
            data = await request.json()
            rpc_request = RequestVoteRequest(**data)
            response = self.node.handle_request_vote(rpc_request)
            return web.json_response(response.model_dump())
        except Exception as e:
            logger.error(f"RequestVote handler error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def handle_append_entries(self, request: web.Request) -> web.Response:
        """Handle AppendEntries RPC."""
        try:
            data = await request.json()
            rpc_request = AppendEntriesRequest(**data)
            response = self.node.handle_append_entries(rpc_request)
            return web.json_response(response.model_dump())
        except Exception as e:
            logger.error(f"AppendEntries handler error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def handle_client_request(self, request: web.Request) -> web.Response:
        """Handle client command request."""
        try:
            command = await request.json()
            
            # Only leader can handle client requests
            if self.node.state.value != "leader":
                # Return leader hint if we know who it is
                return web.json_response(
                    {
                        "error": "not_leader",
                        "message": "Only leader can handle client requests",
                        "current_state": self.node.state.value,
                    },
                    status=503
                )
            
            # Append entry and wait for replication
            success = await self.node.append_entry(command)
            
            if success:
                # Wait for commit (with timeout)
                max_wait = 5.0
                start_time = asyncio.get_event_loop().time()
                
                while asyncio.get_event_loop().time() - start_time < max_wait:
                    if self.node.last_applied >= self.node._get_last_log_index():
                        # Entry has been applied
                        return web.json_response({
                            "status": "ok",
                            "message": "Command applied",
                            "index": self.node._get_last_log_index(),
                        })
                    await asyncio.sleep(0.05)
                
                return web.json_response({
                    "status": "timeout",
                    "message": "Command appended but not yet committed",
                }, status=202)
            
            else:
                return web.json_response({
                    "error": "failed",
                    "message": "Failed to append entry"
                }, status=500)
        
        except Exception as e:
            logger.error(f"Client request handler error: {e}")
            return web.json_response({"error": str(e)}, status=500)
    
    async def handle_status(self, request: web.Request) -> web.Response:
        """Return node status."""
        return web.json_response(self.node.get_status())
    
    async def handle_health(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        return web.json_response({"status": "healthy"})
    
    async def send_rpc(self, peer: str, endpoint: str, data: dict) -> dict:
        """Send RPC request to peer."""
        url = self.node.peer_connections.get(peer)
        if not url:
            raise ValueError(f"No URL for peer {peer}")
        
        full_url = f"{url}/raft/{endpoint}"
        
        try:
            timeout = ClientTimeout(total=1.0)
            async with self.client_session.post(
                full_url,
                json=data,
                timeout=timeout
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    logger.debug(f"RPC to {peer} failed with status {response.status}")
                    return None
        
        except asyncio.TimeoutError:
            logger.debug(f"RPC to {peer} timed out")
            return None
        
        except Exception as e:
            logger.debug(f"RPC to {peer} failed: {e}")
            return None
    
    async def start(self):
        """Start the HTTP server."""
        # Create client session for RPCs
        self.client_session = ClientSession()
        
        # Monkey-patch the node's RPC method
        async def patched_rpc(peer: str, method: str, data: dict):
            return await self.send_rpc(peer, method, data)
        
        self.node._simulate_rpc = patched_rpc
        
        # Start the node
        await self.node.start()
        
        # Start HTTP server
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(
            self.runner,
            self.node.host,
            self.node.port
        )
        await site.start()
        
        logger.info(f"Server started on {self.node.host}:{self.node.port}")
    
    async def stop(self):
        """Stop the HTTP server."""
        await self.node.stop()
        
        if self.client_session:
            await self.client_session.close()
        
        if self.runner:
            await self.runner.cleanup()
        
        logger.info("Server stopped")