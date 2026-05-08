import boto3
import os
import trimesh
import tempfile
import json

LOCAL_TESTING = False

s3 = boto3.client('s3')

def lambda_handler(event, context):
    print("Received event:", event)

    if LOCAL_TESTING:
        print("Running in LOCAL_TESTING mode...")

        local_obj_path = "testmodel.obj"
        if not os.path.exists(local_obj_path):
            print("OBJ file does not exist:", local_obj_path)
            return {
                "statusCode": 404,
                "body": json.dumps("Local OBJ file not found.")
            }

        mesh = trimesh.load(local_obj_path, file_type="obj")
        export_bytes = mesh.export(file_type="glb")  # Now exports as binary GLB

        output_path = os.path.join(os.path.dirname(local_obj_path), "test_output.glb")
        with open(output_path, "wb") as f:
            f.write(export_bytes)

        print("Local test successful, output written to:", output_path)

        return {"statusCode": 200, "body": f"Local GLB written to: {output_path}"}

    # ---------------- Production Path ----------------
    bucket = event['Records'][0]['s3']['bucket']['name']
    obj_key = event['Records'][0]['s3']['object']['key']

    if not obj_key.lower().endswith('.obj'):
        print("Not an .obj file, exiting.")
        return {
            "statusCode": 200,
            "body": json.dumps("Skipped non-OBJ file.")
        }

    obj_basename = os.path.splitext(os.path.basename(obj_key))[0]
    glb_key = f"streamables/{obj_basename}.glb"

    try:
        s3.head_object(Bucket=bucket, Key=glb_key)
        print(f"{glb_key} already exists, skipping conversion.")
        return {
            "statusCode": 200,
            "body": json.dumps("GLB already exists.")
        }
    except Exception as e:
        if not hasattr(e, 'response') or e.response.get('Error', {}).get('Code') != '404':
            raise
        print("GLB not found ??? proceeding with conversion.")

    with tempfile.TemporaryDirectory() as tmpdir:
        obj_path = os.path.join(tmpdir, 'model.obj')
        glb_path = os.path.join(tmpdir, 'model.glb')

        s3.download_file(bucket, obj_key, obj_path)

        with open(obj_path, "rb") as file_obj:
            mesh = trimesh.load(file_obj, file_type='obj')
            export_bytes = mesh.export(file_type="glb")

        with open(glb_path, 'wb') as f:
            f.write(export_bytes)

        s3.upload_file(glb_path, bucket, glb_key)
        print(f"Uploaded {glb_key} to {bucket}")

        return {
            "statusCode": 200,
            "body": json.dumps(f"Uploaded {glb_key} to {bucket}")
        }
