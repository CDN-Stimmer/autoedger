import os
import sys
import shutil
import zipfile

def setup_directories():
    """Create required directories for the application."""
    print("Setting up directories for Audio Control application...")
    
    # Create required directories
    directories = [
        "src/data/audio",
        "src/data/model",
        "src/data/logs",
        "src/data/logs/peak_performers",
        "src/data/favorites"
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"Created directory: {directory}")
    
    # Create .gitkeep files to ensure empty directories are tracked in Git
    for directory in directories:
        gitkeep_file = os.path.join(directory, ".gitkeep")
        with open(gitkeep_file, 'w') as f:
            pass
        print(f"Created .gitkeep file in {directory}")
    
    return True

def extract_model(model_zip_path):
    """Extract the Vosk model to the correct location."""
    if not os.path.exists(model_zip_path):
        print(f"Error: Model file {model_zip_path} not found!")
        print("Please download the model from https://alphacephei.com/vosk/models")
        print("Recommended model: vosk-model-small-en-us-0.15.zip")
        return False
    
    model_dir = "src/data/model"
    
    print(f"Extracting model from {model_zip_path} to {model_dir}...")
    try:
        with zipfile.ZipFile(model_zip_path, 'r') as zip_ref:
            # Get the name of the top directory in the ZIP file
            top_dir = zip_ref.namelist()[0].split('/')[0]
            
            # Extract the ZIP file
            zip_ref.extractall("src/data")
            
            # If the model was extracted to a subdirectory, move its contents up
            extracted_dir = os.path.join("src/data", top_dir)
            if os.path.exists(extracted_dir) and os.path.isdir(extracted_dir):
                # Remove existing files in model_dir 
                for item in os.listdir(model_dir):
                    item_path = os.path.join(model_dir, item)
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                
                # Move files from extracted_dir to model_dir
                for item in os.listdir(extracted_dir):
                    src_path = os.path.join(extracted_dir, item)
                    dst_path = os.path.join(model_dir, item)
                    shutil.move(src_path, dst_path)
                
                # Remove the now-empty extracted directory
                shutil.rmtree(extracted_dir)
                
        print("Model extracted successfully!")
        return True
    except Exception as e:
        print(f"Error extracting model: {e}")
        return False

def main():
    """Main setup function."""
    print("==== Audio Control Application Setup ====")
    
    # Set up directories
    if not setup_directories():
        print("Failed to set up directories. Exiting.")
        return 1
    
    # Check for model file
    model_file = "vosk-model-small-en-us-0.15.zip"
    if os.path.exists(model_file):
        if extract_model(model_file):
            print(f"Model {model_file} extracted successfully.")
        else:
            print(f"Failed to extract model {model_file}.")
    else:
        print(f"Model file {model_file} not found in current directory.")
        print("You will need to download the model from https://alphacephei.com/vosk/models")
        print("and extract it to src/data/model manually.")
    
    print("\nSetup completed. You can now run the application with:")
    print("python src/main.py")
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 