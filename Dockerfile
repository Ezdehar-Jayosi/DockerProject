FROM alpine

# Install Docker CLI
RUN apk add --no-cache docker-cli

# Copy the script to the container
COPY init-replica-set.sh /init-replica-set.sh
RUN chmod +x /init-replica-set.sh

# Command to run the script
CMD ["sh", "-c", "/bin/sh /init-replica-set.sh"]


