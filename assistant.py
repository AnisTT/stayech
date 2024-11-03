from flask import jsonify, request
import google.generativeai as genai
import os
import requests
import json
from dotenv import load_dotenv

load_dotenv()

# Configure the Gemini API
genai.configure(api_key=os.environ["GEMINI_API_KEY"])
model = genai.GenerativeModel("gemini-1.5-flash")

class Assistant:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set in the environment variables.")
        self.history = []  # Initialize history for each instance

    def get_recommendations(self, user_data):
        """
        Fetch recommendations based on user data.
        
        Args:
            user_data (dict): A dictionary containing user transactions and income data.
        
        Returns:
            dict: Recommendations or an error message.
        """
        # Convert user_data to a string format expected by the model
        user_data_str = json.dumps(user_data)

        # Log the user data for debugging
        print("User Data Sent to Model:", user_data_str)

        # Append the user data to the chat history
        self.history.append({"role": "user", "parts": [{"text": user_data_str}]})

        try:
            chat = model.start_chat(history=self.history)
            # Send a tailored message asking for recommendations
            message = (
                "Based on the following user data, please provide tailored financial recommendations in 5 lines and don't redisplay the data. "
                "Consider the user's spending habits, income sources, and any financial goals they might have. "
                "The user is looking for advice on how to manage their finances better. "
                "The user is open to suggestions on how to save more money and invest wisely. "
                "Here’s the user data: " + user_data_str  # Include user data in the message
            )
            response = chat.send_message(message)
            # Append the model's response to the history
            self.history.append({"role": "model", "parts": [{"text": response.text}]})

            # Limit the response to the first 5 lines and format it
            limited_response = "".join(response.text.splitlines()[:5])
            formatted_response = f"{limited_response}"  # Optional formatting
            
            return formatted_response
        except requests.exceptions.RequestException as e:
            return {"error": str(e)}
        except Exception as e:
            return {"error": f"An unexpected error occurred: {str(e)}"}
        
    def send_message(self, message):
        if not message:
            return "No message provided.", self.history
        
        self.history.append({"role": "user", "parts": [{"text": message}]})
        chat = model.start_chat(history=self.history)
        response = chat.send_message(message)
        
        if hasattr(response, 'text'):
            self.history.append({"role": "model", "parts": [{"text": response.text}]})
            return response.text, self.history
        else:
            return "No response from the model.", self.history

    def chat(self):
        user_message = request.json.get('message')
        history = request.json.get('history', self.history)  # Use existing history if not provided
        response, history = self.send_message(user_message)
        return jsonify({'message': response, "history": history})
