# Dockerfile 

# An official Python runtime as a parent image
# is not working on raspberry pi with pandas
#FROM python:3.6.9-slim
# so let's use pri_docker_base
# https://github.com/azogue/rpi_docker_base
FROM azogue/py36_base:rpi3

# Set the working directory to / 
# in the container
WORKDIR /app/

# Copy the python script
COPY app/* /app/

# Install any needed packages specified in requirements.txt
RUN pip install --trusted-host pypi.python.org -r requirements.txt


# Run app.py when the container launches
# The -u flag specifies to use the unbuffered ouput.
# in this way, what's printed by the app is visible on the host
# while the container is running
#CMD ["python", "-u", "app.py"]
CMD ["ls", "-la"]

