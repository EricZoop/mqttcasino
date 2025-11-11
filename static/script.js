// Wait for the entire HTML document to be loaded before running the script
document.addEventListener('DOMContentLoaded', () => {

    // Get references to the HTML elements
    const messageForm = document.getElementById('message-form');
    const messageInput = document.getElementById('message-input');
    const statusMessage = document.getElementById('status-message');
    const submitButton = document.getElementById('submit-button');

    // Check if all elements were found
    if (!messageForm || !messageInput || !statusMessage || !submitButton) {
        console.error("Error: Could not find one or more required HTML elements.");
        if (statusMessage) {
            statusMessage.textContent = "Error: Page elements missing. Please reload.";
            statusMessage.className = "status-error";
        }
        return; // Stop if elements are missing
    }

    // Add a 'submit' event listener to the form
    messageForm.addEventListener('submit', async (event) => {
        
        // Prevent the form's default 'GET' submission, which reloads the page
        event.preventDefault(); 

        // Get the text from the input box
        const message = messageInput.value.trim();
        if (!message) {
            statusMessage.textContent = "Please enter a message.";
            statusMessage.className = "status-error";
            return;
        }

        // Disable the button and show loading text
        submitButton.disabled = true;
        submitButton.textContent = "Sending...";
        statusMessage.textContent = "Sending...";
        statusMessage.className = "status-sending";

        try {
            // Use the 'fetch' API to send a POST request to our Flask server
            const response = await fetch('/send_message', {
                method: 'POST',
                // We need to send the data as 'FormData' to match request.form.get() in Flask
                body: new FormData(messageForm) 
            });

            // Get the JSON response from the server
            const result = await response.json();

            // Check if the server reported success
            if (response.ok && result.status === 'success') {
                console.log("Message sent successfully:", result.message);
                statusMessage.textContent = `Successfully sent: "${result.message}"`;
                statusMessage.className = "status-success";
                messageInput.value = ""; // Clear the input box
            } else {
                // Show an error message if the server reported an error
                console.error("Server error:", result.message);
                statusMessage.textContent = `Error: ${result.message}`;
                statusMessage.className = "status-error";
            }

        } catch (error) {
            // Show a message if there was a network error (e.g., server is down)
            console.error("Fetch error:", error);
            statusMessage.textContent = "Network error. Is the server running?";
            statusMessage.className = "status-error";
        } finally {
            // Re-enable the button regardless of success or failure
            submitButton.disabled = false;
            submitButton.textContent = "Send Message";
        }
    });
});