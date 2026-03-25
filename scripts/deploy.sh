#!/bin/bash

# Configuration (These should be provided via environment variables in GitHub Actions)
# DO_HOST
# DO_USER
# DO_SSH_KEY (Path to the SSH key file or content)
# DO_PATH (Path to the .env file on the server)
# NEW_MODEL_ID (The ID of the new fine-tuned model)

if [ -z "$NEW_MODEL_ID" ]; then
    echo "Error: NEW_MODEL_ID is not set."
    exit 1
fi

echo "Deploying new model ID: $NEW_MODEL_ID to $DO_HOST..."

# Create a temporary SSH key if it's passed as content
if [ -n "$DO_SSH_KEY_CONTENT" ]; then
    mkdir -p ~/.ssh
    echo "$DO_SSH_KEY_CONTENT" > ~/.ssh/id_ed25519
    chmod 600 ~/.ssh/id_ed25519
fi

# Use SSH to update the .env file on the server
ssh -o StrictHostKeyChecking=no "$DO_USER@$DO_HOST" << ENDSSH
  if [ -f "$DO_PATH" ]; then
    # Backup the .env file
    cp "$DO_PATH" "${DO_PATH}.bak"
    # Update the GEMINI_FEEDBACK_MODEL variable (using | delimiter to avoid conflicts with / in model ID)
    sed -i "s|^GEMINI_FEEDBACK_MODEL=.*|GEMINI_FEEDBACK_MODEL=$NEW_MODEL_ID|" "$DO_PATH"
    echo "Updated GEMINI_FEEDBACK_MODEL in $DO_PATH"

    # Get the app directory from the .env path
    APP_DIR=\$(dirname "$DO_PATH")
    echo "App directory: \$APP_DIR"

    # Stop the running uvicorn process
    echo "Stopping existing uvicorn process..."
    pkill -f "uvicorn app.main:app" || echo "No existing uvicorn process found"
    sleep 2

    # Restart uvicorn using the venv
    echo "Restarting uvicorn..."
    cd "\$APP_DIR"

    # Activate venv and start uvicorn
    if [ -d "\$APP_DIR/venv" ]; then
      PYTHON="\$APP_DIR/venv/bin/python"
    elif [ -d "\$APP_DIR/.venv" ]; then
      PYTHON="\$APP_DIR/.venv/bin/python"
    else
      PYTHON="python"
    fi

    nohup env PYTHONPATH=. \$PYTHON -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > uvicorn.log 2>&1 &
    sleep 3

    # Verify it's running
    if pgrep -f "uvicorn app.main:app" > /dev/null; then
      echo "Uvicorn restarted successfully (PID: \$(pgrep -f 'uvicorn app.main:app'))"
    else
      echo "Error: Uvicorn failed to start. Last 10 lines of uvicorn.log:"
      tail -10 uvicorn.log
      exit 1
    fi
  else
    echo "Error: .env file not found at $DO_PATH"
    exit 1
  fi
ENDSSH

if [ $? -eq 0 ]; then
    echo "Deployment successful!"
else
    echo "Deployment failed."
    exit 1
fi