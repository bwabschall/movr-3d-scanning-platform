FROM public.ecr.aws/lambda/python:3.9

# Install system dependencies (trimesh sometimes needs them)
RUN yum install -y \
    libGL \
    && yum clean all

# Upgrade pip and install Python packages
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Add your lambda code
COPY lambda_function.py ./

# Set the entrypoint
CMD ["lambda_function.lambda_handler"]
