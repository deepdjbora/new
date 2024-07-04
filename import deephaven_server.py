import deephaven_server

server = deephaven_server.Server(port=10000, jvm_args=["-Xmx4g"])  # Adjust memory as needed
server.start()

import deephaven as dh  # Import Deephaven modules after starting the server

