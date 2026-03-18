import asyncio

import pytest

from mcp_sdk.core import PluginManager, PluginRegistry


@pytest.mark.asyncio
async def test_auth_plugin() -> None:
    print("\nStarting Auth Plugin and Isolation verification...")

    registry = PluginRegistry()
    manager = PluginManager(registry)

    # Ensure auth is enabled
    manager.state.set_plugin_enabled("auth", True)

    # 1. Test LOCAL execution (default)
    print("\n--- Testing LOCAL execution ---")
    await manager.load_and_activate_all()

    create_token = registry.get_tool("auth.create_token")
    verify_token = registry.get_tool("auth.verify_token")
    check_perm = registry.get_tool("auth.check_permission")

    token = await create_token(user_id="alice", roles=["admin"])
    print(f"Token created: {token[:20]}...")

    # Assign ROLE to Alice in RBAC manager
    assign_role = registry.get_tool("auth.assign_role")
    await assign_role(user_id="alice", role_name="admin")

    is_valid = await verify_token(token=token)
    print(f"Token valid: {is_valid}")
    assert is_valid is True

    has_access = await check_perm(user_id="alice", resource="*", action="*")
    print(f"Alice has admin access: {has_access}")
    assert has_access is True

    # 2. Test SUBPROCESS isolation
    print("\n--- Testing SUBPROCESS isolation ---")
    # Switch auth plugin to subprocess isolation
    auth_manifest_path = manager.plugin_dir / "auth" / "plugin.yaml"
    with open(auth_manifest_path) as f:
        manifest_text = f.read()

    with open(auth_manifest_path, "w") as f:
        f.write(manifest_text.replace("isolation: local", "isolation: subprocess"))

    try:
        # Reload to apply isolation change
        await manager.reload_plugin("auth")

        create_token_iso = registry.get_tool("auth.create_token")
        token_iso = await create_token_iso(user_id="bob", roles=["viewer"])
        print(f"Isolated Token created: {token_iso[:20]}...")

        # Assign ROLE to Bob in isolated RBAC manager
        assign_role_iso = registry.get_tool("auth.assign_role")
        await assign_role_iso(user_id="bob", role_name="viewer")

        is_valid_iso = await registry.get_tool("auth.verify_token")(token=token_iso)
        print(f"Isolated Token valid: {is_valid_iso}")
        assert is_valid_iso is True

        has_access_iso = await registry.get_tool("auth.check_permission")(
            user_id="bob", resource="agents", action="read"
        )
        print(f"Bob has read access: {has_access_iso}")
        assert has_access_iso is True

        print("\nSUCCESS: Auth plugin and isolation verified in both modes!")

    finally:
        # Restore local isolation for safety
        with open(auth_manifest_path, "w") as f:
            f.write(manifest_text)


if __name__ == "__main__":
    asyncio.run(test_auth_plugin())
