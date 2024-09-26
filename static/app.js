function tradeDashboard() {
    return {
        currentPositions: [],
        historicalPositions: [],
        ws: null,

        // Initialize WebSocket and functions
        init() {
            console.log("Initializing WebSocket...");
            this.connectWebSocket();
        },

        // Connect to the WebSocket server
        connectWebSocket() {
            this.ws = new WebSocket("ws://localhost:8000/ws/trade_updates");

            // Handle WebSocket connection open
            this.ws.onopen = () => {
                console.log("WebSocket connected.");
            };

            // Handle incoming messages from WebSocket
            this.ws.onmessage = (event) => {
                console.log("WebSocket Message Received: ", event.data);  // Log received data

                const data = JSON.parse(event.data);

                if (data.event === "trade_updated") {
                    console.log("Processing trade updates...");

                    // Find the position in currentPositions array
                    const positionIndex = this.currentPositions.findIndex(pos => pos.trade_id === data.data.trade_id);

                    if (positionIndex !== -1) {
                        // Update the existing position
                        this.currentPositions[positionIndex] = data.data;
                    } else {
                        // Add new position if not found
                        this.currentPositions.push(data.data);
                    }
                } else if (data.event === "trade_entered") {
                    console.log("Processing trade entered...");
                    // Handle trade entered event
                    this.currentPositions.push(data.data);
                } else if (data.event === "trade_exited") {
                    console.log("Processing trade exited...");
                    // Handle trade exited event
                    this.currentPositions = this.currentPositions.filter(pos => pos.trade_id !== data.data.trade_id);

                    // Ensure all necessary fields are included in the historical position
                    const historicalPosition = {
                        trade_id: data.data.trade_id,
                        symbol_name: data.data.symbol_name,
                        entry_price: data.data.entry_price,
                        entry_time: data.data.entry_time,
                        exit_time: data.data.exit_time,
                        exit_type: data.data.exit_reason,
                        pnl: data.data.profit_loss
                    };

                    this.historicalPositions.push(historicalPosition);
                } else {
                    console.log("Unknown event: ", data.event);
                }
            };

            // Handle WebSocket errors
            this.ws.onerror = (error) => {
                console.error("WebSocket error: ", error);
            };

            // Reconnect WebSocket when it's closed
            this.ws.onclose = () => {
                console.warn("WebSocket closed, reconnecting...");
                setTimeout(() => this.connectWebSocket(), 3000);  // Retry in 3 seconds
            };
        },

        // Define button actions (FastAPI endpoints)
        enablePut() {
            fetch('/enable_put', { method: 'POST' });
        },
        enableCall() {
            fetch('/enable_call', { method: 'POST' });
        },
        enableBoth() {
            fetch('/enable_both', { method: 'POST' });
        },
        forceExit() {
            fetch('/force_exit', { method: 'POST' });
        }
    };
}