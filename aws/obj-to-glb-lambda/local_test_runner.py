import lambda_function
import json
import os

def mock_s3_event(bucket_name, key):
    return {
        "Records": [
            {
                "s3": {
                    "bucket": {
                        "name": bucket_name
                    },
                    "object": {
                        "key": key
                    }
                }
            }
        ]
    }

if __name__ == "__main__":
    # Configure your local test .obj file path
    test_bucket = "local-bucket"
    test_obj_key = "testmodel.obj"
    test_obj_path = os.path.join(os.getcwd(), test_obj_key)

    # Ensure the file exists before testing
    if not os.path.exists(test_obj_path):
        print(f"❌ ERROR: Test OBJ file not found at {test_obj_path}")
        exit(1)

    # Create a fake S3 "download"
    os.makedirs("tmp_s3/objects", exist_ok=True)
    fake_s3_path = os.path.join("tmp_s3", "objects", test_obj_key)
    os.system(f"cp {test_obj_path} {fake_s3_path}")  # Unix-style copy (works on WSL/mac/Linux)

    # Patch boto3 S3 client
    import boto3
    from unittest.mock import MagicMock

    fake_s3 = MagicMock()

    def fake_download_file(Bucket, Key, Filename):
        local_path = os.path.join("tmp_s3", Key)
        os.system(f"cp {local_path} {Filename}")

    def fake_upload_file(Filename, Bucket, Key):
        print(f"📦 Simulated upload to: {Bucket}/{Key}")
        print(f"File contents (first 200 bytes):")
        with open(Filename, 'rb') as f:
            print(f.read(200))

    def fake_head_object(Bucket, Key):
        raise boto3.client("s3").exceptions.ClientError(
            error_response={"Error": {"Code": "404", "Message": "Not Found"}},
            operation_name="HeadObject"
        )

    fake_s3.download_file.side_effect = fake_download_file
    fake_s3.upload_file.side_effect = fake_upload_file
    fake_s3.head_object.side_effect = fake_head_object

    lambda_function.s3 = fake_s3

    # Run the handler
    print("🚀 Running local test...")
    result = lambda_function.lambda_handler(mock_s3_event(test_bucket, f"objects/{test_obj_key}"), {})
    print("✅ Lambda handler result:")
    print(json.dumps(result, indent=2))
