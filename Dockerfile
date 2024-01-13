# Start from the latest python base image
FROM python:3.11

WORKDIR /usr/app

COPY ./apple-home-key-reader/* .

# Define environment veriables
ENV TZ="Europe/London"

# Create Environment veriable logging level
ENV LOG_LEVEL="INFO"

#Update pip
RUN pip install --upgrade pip

#Install the Python dependancies
RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 51926

# Create health check to check / url
#HEALTHCHECK --interval=5m --timeout=3s --start-period=10s --retries=3 CMD curl -f http://localhost:8080/ || exit 1

CMD ["python3", "./main.py"]