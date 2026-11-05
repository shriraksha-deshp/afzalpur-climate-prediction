import os
import subprocess

def run():
    scripts_dir = os.path.dirname(__file__)
    print("Executing forecast engine...")
    subprocess.run(["python", os.path.join(scripts_dir, "forecast_engine.py")], check=True)
    print("Pipeline executed successfully.")

if __name__ == "__main__":
    run()
