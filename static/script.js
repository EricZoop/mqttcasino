document.addEventListener('DOMContentLoaded', () => {
    const startButton = document.getElementById('start-button');
    const stopButton = document.getElementById('stop-button');
    const statusMessage = document.getElementById('status-message');

    // Handle Start Button click
    startButton.addEventListener('click', async () => {
        try {
            const response = await fetch('/start', { method: 'POST' });
            const data = await response.json();
            
            if (data.status === 'started') {
                statusMessage.textContent = 'Status: Sending...';
                statusMessage.style.color = 'green';
            }
        } catch (error) {
            statusMessage.textContent = 'Error starting.';
            statusMessage.style.color = 'red';
        }
    });

    // Handle Stop Button click
    stopButton.addEventListener('click', async () => {
        try {
            const response = await fetch('/stop', { method: 'POST' });
            const data = await response.json();
            
            if (data.status === 'stopped') {
                statusMessage.textContent = 'Status: Stopped.';
                statusMessage.style.color = 'orange';
            }
        } catch (error) {
            statusMessage.textContent = 'Error stopping.';
            statusMessage.style.color = 'red';
        }
    });
});