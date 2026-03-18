import os
import subprocess
import sys


def generate_proto():
    proto_path = "mcp-core-rust/proto/plugin.proto"
    output_path = "mcp_sdk/core/generated"

    if not os.path.exists(output_path):
        os.makedirs(output_path)
        with open(os.path.join(output_path, "__init__.py"), "w") as f:
            pass

    print(f"Generating Python gRPC code from {proto_path}...")

    cmd = [
        sys.executable, "-m", "grpc_tools.protoc",
        f"-I{os.path.dirname(proto_path)}",
        f"--python_out={output_path}",
        f"--grpc_python_out={output_path}",
        os.path.basename(proto_path)
    ]

    try:
        subprocess.run(cmd, check=True)
        print(f"Success! Generated code in {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error generating proto: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == "__main__":
    generate_proto()
