FROM public.ecr.aws/lambda/python:3.11

# Install required system dependencies for Playwright
# NOTE: The lambda/python image is minimal. Playwright needs a lot of libs.
# We often need to use a custom base or install these via apt.
# However, AWS Lambda container images are based on Amazon Linux 2 or 2023 usually, not Ubuntu/Jammy.
# The 'mcr.microsoft.com/playwright/python' is Ubuntu based.
# To make this easier, we can use the Microsoft image as the base and add the Lambda RIC (Runtime Interface Client).

FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy

# Install Lambda Runtime Interface Client
RUN pip install awslambdaric

# Set working directory
WORKDIR /var/task

# Copy function code and requirements
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY lambda_function.py .
COPY database.py .

# Entry point for Lambda
ENTRYPOINT [ "python", "-m", "awslambdaric" ]
CMD [ "lambda_function.handler" ]
