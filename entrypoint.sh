#!/bin/bash

# Execute nearai login with environment variables
nearai login --accountId "$INTENT_ACCOUNT_ID" --privateKey "$INTENT_PRIVATE_KEY"

# Execute the command passed to docker run
exec "$@" 