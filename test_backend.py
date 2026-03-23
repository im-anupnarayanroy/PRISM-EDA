import requests

# The PriSm API endpoint
URL = "http://127.0.0.1:8000/process_data"

# The text and configuration data we want to send
payload = {
    "problem_statement": "Testing the PriSm backend with supply chain data.",
    "plot_types": "Histogram,Scatter Plot,Bar Chart"
}

# The target dataset
file_path = "supply_chain_data.csv"

def run_test():
    try:
        # Open the CSV file in binary read mode
        with open(file_path, "rb") as f:
            # Prepare the file payload for a multipart/form-data request
            files = {"file": (file_path, f, "text/csv")}
            
            print(f"Sending request to {URL}...")
            
            # Make the POST request
            response = requests.post(URL, data=payload, files=files)
            
            # Evaluate the response
            if response.status_code == 200:
                print("\n✅ Success! API is working perfectly.\n")
                
                # Parse the JSON response
                response_json = response.json()
                
                print(f"Message: {response_json.get('message')}")
                print(f"Problem Statement Acknowledged: {response_json.get('problem_statement_received')}")
                
                # Check how many plots were generated
                plots = response_json.get('plots', [])
                print(f"Number of plots successfully generated and encoded: {len(plots)}")
                
                if len(plots) > 0:
                    print("(The base64 image strings are ready to be rendered by the frontend!)")
            else:
                print(f"\n❌ Error {response.status_code}: Something went wrong.")
                print(response.text)
                
    except FileNotFoundError:
        print(f"\n❌ Error: Could not find '{file_path}'. Ensure it is in the current directory.")
    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to the API. Is the Uvicorn server running on port 8000?")

if __name__ == "__main__":
    run_test()