"""
Run a single Raft node.
"""

import asyncio
import logging
import signal
from pathlib import Path

import click

from raft import RaftNode
from server import RaftServer


@click.command()
@click.option('--node-id', required=True, help='Unique node identifier')
@click.option('--port', type=int, required=True, help='HTTP port')
@click.option('--peers', required=True, help='Comma-separated list of peer IDs')
@click.option('--storage-dir', required=True, help='Directory for persistent storage')
@click.option('--host', default='localhost', help='Host to bind to')
@click.option('--election-timeout-min', default=150, help='Min election timeout (ms)')
@click.option('--election-timeout-max', default=300, help='Max election timeout (ms)')
@click.option('--heartbeat-interval', default=50, help='Heartbeat interval (ms)')
@click.option('--log-level', default='INFO', help='Logging level')
def main(
    node_id: str,
    port: int,
    peers: str,
    storage_dir: str,
    host: str,
    election_timeout_min: int,
    election_timeout_max: int,
    heartbeat_interval: int,
    log_level: str,
):
    """Run a Raft node."""
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Parse peers
    peer_list = [p.strip() for p in peers.split(',') if p.strip()]
    
    # Create node
    node = RaftNode(
        node_id=node_id,
        peers=peer_list,
        storage_dir=Path(storage_dir),
        host=host,
        port=port,
        election_timeout_min=election_timeout_min,
        election_timeout_max=election_timeout_max,
        heartbeat_interval=heartbeat_interval,
    )
    
    # Create server
    server = RaftServer(node)
    
    # Setup graceful shutdown
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    async def shutdown(sig):
        """Graceful shutdown handler."""
        print(f"\nReceived signal {sig.name}, shutting down...")
        await server.stop()
        loop.stop()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(shutdown(s))
        )
    
    # Start server
    try:
        loop.run_until_complete(server.start())
        print(f"Node {node_id} running on {host}:{port}")
        loop.run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(server.stop())
        loop.close()


if __name__ == '__main__':
    main()
