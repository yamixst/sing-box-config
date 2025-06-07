#!/usr/bin/env python3
import struct
import gzip
import io
import argparse
import sys


class ProfileContent:
    PROFILE_TYPE_LOCAL = 0
    PROFILE_TYPE_ICLOUD = 1
    PROFILE_TYPE_REMOTE = 2
    MESSAGE_TYPE_PROFILE_CONTENT = 3

    def __init__(self,
                 name: str,
                 profile_type: int,
                 config: str,
                 remote_path: str = "",
                 auto_update: bool = False,
                 auto_update_interval: int = 0,
                 last_updated: int = 0):
        self.name = name
        self.type = profile_type
        self.config = config
        self.remote_path = remote_path
        self.auto_update = auto_update
        self.auto_update_interval = auto_update_interval
        self.last_updated = last_updated


def write_uvarint(writer: io.BytesIO, value: int) -> int:
    written = 0
    while value >= 0x80:
        writer.write(struct.pack('B', (value & 0x7F) | 0x80))
        value >>= 7
        written += 1
    writer.write(struct.pack('B', value & 0x7F))
    return written + 1


def write_varbin_string(writer: io.BytesIO, value: str) -> None:
    encoded = value.encode('utf-8')
    length = len(encoded)
    write_uvarint(writer, length)
    if length > 0:
        writer.write(encoded)

def encode_profile_content(profile: ProfileContent) -> bytes:
    buffer = io.BytesIO()
    buffer.write(struct.pack('B', ProfileContent.MESSAGE_TYPE_PROFILE_CONTENT))
    buffer.write(struct.pack('B', 1))
    compressed_buffer = io.BytesIO()

    with gzip.GzipFile(fileobj=compressed_buffer, mode='wb') as gzip_writer:
        inner_buffer = io.BytesIO()
        write_varbin_string(inner_buffer, profile.name)
        inner_buffer.write(struct.pack('>i', profile.type))
        write_varbin_string(inner_buffer, profile.config)
        if profile.type != ProfileContent.PROFILE_TYPE_LOCAL:
            write_varbin_string(inner_buffer, profile.remote_path)
        if profile.type == ProfileContent.PROFILE_TYPE_REMOTE:
            inner_buffer.write(struct.pack('?', profile.auto_update))
            inner_buffer.write(struct.pack('>i', profile.auto_update_interval))
            inner_buffer.write(struct.pack('>q', profile.last_updated))
        gzip_writer.write(inner_buffer.getvalue())
    buffer.write(compressed_buffer.getvalue())

    return buffer.getvalue()


def create_local_profile(name: str, config: str) -> ProfileContent:
    return ProfileContent(
        name=name,
        profile_type=ProfileContent.PROFILE_TYPE_LOCAL,
        config=config
    )


def create_remote_profile(name: str, config: str, remote_path: str,
                         auto_update: bool = False,
                         auto_update_interval: int = 3600,
                         last_updated: int = 0) -> ProfileContent:
    return ProfileContent(
        name=name,
        profile_type=ProfileContent.PROFILE_TYPE_REMOTE,
        config=config,
        remote_path=remote_path,
        auto_update=auto_update,
        auto_update_interval=auto_update_interval,
        last_updated=last_updated
    )


def create_icloud_profile(name: str, config: str, remote_path: str) -> ProfileContent:
    return ProfileContent(
        name=name,
        profile_type=ProfileContent.PROFILE_TYPE_ICLOUD,
        config=config,
        remote_path=remote_path
    )


def main():
    parser = argparse.ArgumentParser(
        description="Encode ProfileContent to binary format matching Go sing-box implementation"
    )

    parser.add_argument(
        "--name",
        help="Profile name (defaults to config filename if not specified)"
    )

    parser.add_argument(
        "--config",
        required=True,
        help="Configuration content (JSON string or file path)"
    )

    parser.add_argument(
        "--type",
        choices=["local", "remote", "icloud"],
        default="local",
        help="Profile type (default: local)"
    )

    parser.add_argument(
        "--remote-path",
        help="Remote path (required for remote and icloud profiles)"
    )

    parser.add_argument(
        "--remotepath",
        help="Remote path (alias for --remote-path)"
    )

    parser.add_argument(
        "--auto-update",
        action="store_true",
        help="Enable auto update (for remote profiles)"
    )

    parser.add_argument(
        "--autoupdate",
        action="store_true",
        help="Enable auto update (alias for --auto-update)"
    )

    parser.add_argument(
        "--auto-update-interval",
        type=int,
        default=0,
        help="Auto update interval in seconds (default: 0)"
    )

    parser.add_argument(
        "--autoupdateinterval",
        type=int,
        default=0,
        help="Auto update interval in seconds (alias for --auto-update-interval)"
    )

    parser.add_argument(
        "--lastupdated",
        type=int,
        default=0,
        help="Last updated timestamp (default: 0)"
    )

    parser.add_argument(
        "--output",
        "-o",
        help="Output file path (default: stdout as hex)"
    )

    args = parser.parse_args()

    remote_path = args.remote_path or args.remotepath or ""
    auto_update = args.auto_update or args.autoupdate
    auto_update_interval = args.autoupdateinterval if args.autoupdateinterval != 0 else args.auto_update_interval
    last_updated = args.lastupdated

    if args.type in ["remote", "icloud"] and not remote_path:
        print("Error: --remote-path or --remotepath is required for remote and icloud profiles", file=sys.stderr)
        sys.exit(1)

    config_content = args.config
    config_file_path = None
    try:
        if config_content.startswith(("./", "/", "~/")) or config_content.endswith(".json"):
            config_file_path = config_content
            with open(config_content, "r", encoding="utf-8") as f:
                config_content = f.read()
    except (FileNotFoundError, PermissionError):
        pass

    profile_name = args.name
    if not profile_name and config_file_path:
        import os
        profile_name = os.path.splitext(os.path.basename(config_file_path))[0]

    if not profile_name:
        print("Error: --name is required when config is not a file", file=sys.stderr)
        sys.exit(1)

    if args.type == "local":
        profile = create_local_profile(profile_name, config_content)
    elif args.type == "remote":
        import time
        profile = create_remote_profile(
            name=profile_name,
            config=config_content,
            remote_path=remote_path,
            auto_update=auto_update,
            auto_update_interval=auto_update_interval,
            last_updated=last_updated if last_updated != 0 else int(time.time())
        )
    elif args.type == "icloud":
        profile = create_icloud_profile(
            name=profile_name,
            config=config_content,
            remote_path=remote_path
        )

    encoded_data = encode_profile_content(profile)

    if args.output:
        output_path = args.output
    elif config_file_path:
        import os
        base_name = os.path.splitext(config_file_path)[0]
        output_path = base_name + ".bpf"
    else:
        output_path = None

    if output_path:
        with open(output_path, "wb") as f:
            f.write(encoded_data)
        print(f"Encoded profile saved to: {output_path}")
        print(f"Size: {len(encoded_data)} bytes")
    else:
        print(encoded_data.hex())

if __name__ == "__main__":
    main()
