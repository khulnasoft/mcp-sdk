import asyncio
import sys
import types


# 1. Mock 'mcp'
class Stub:
    def __init__(self, *args, **kwargs): pass
    def __getattr__(self, name):
        if name.startswith('__'): raise AttributeError(name)
        return Stub()
    def __call__(self, *args, **kwargs): return Stub()

class MockModule(types.ModuleType):
    def __getattr__(self, name):
        if name.startswith('__'): return super().__getattr__(name)
        return Stub()

def create_mock_module(name):
    m = MockModule(name)
    sys.modules[name] = m
    return m

create_mock_module('mcp')
create_mock_module('mcp.server')
create_mock_module('mcp.server.models')
create_mock_module('mcp.client')
create_mock_module('mcp.client.session')
create_mock_module('mcp.types')

# 2. Import Modules Directly
from mcp_sdk.plugins.active_inference.active_inference import (
    ActiveInferenceEngine,
    BeliefState,
    GenerativeModel,
)
from mcp_sdk.plugins.context.manager import TokenBudgetManager
from mcp_sdk.plugins.geospatial.model import GeoPoint, LargeGeospatialModel
from mcp_sdk.plugins.loop.engine import ObservationActionLoop


async def run_smoke_test():
    print("✅ Smoke test: Starting...")

    # 3. Test Active Inference

    model = GenerativeModel(state_dim=2)
    belief = BeliefState(dim=2, mean=[0.5, 0.5], variance=[0.1, 0.1])
    engine = ActiveInferenceEngine(state_dim=2, action_space=["move", "hover"], generative_model=model)

    # Test infer loop
    result = await engine.infer(observation=[0.1, 0.2])
    print(f"✅ Active Inference: Result action = {result.action} (surprise: {result.surprise:.2f})")

    # 4. Test Geospatial
    geo = LargeGeospatialModel()
    point = GeoPoint(lat=37.7749, lon=-122.4194)
    h3_idx = geo.index_point(point)
    print(f"✅ Geospatial: Point indexed to {h3_idx}")

    # 5. Test Token Manager (Context)
    from mcp_sdk.plugins.context.manager import ContextItem
    tm = TokenBudgetManager(max_tokens=1000)
    tm.add(ContextItem(content="Hello world", priority=1.0))
    print(f"✅ Token Budget Manager: Usage = {tm.token_usage} tokens")

    # 6. Test Loop (Instantiate only)
    loop = ObservationActionLoop()
    print("✅ Observation-Action Loop: Engine instantiated.")

    # 7. Test Metadata Plugin (New implementation)
    from mcp_sdk.plugins.metadata.registry import DataSource, MetadataRegistry, SourceType
    meta_reg = MetadataRegistry()
    src_id = meta_reg.register_source(DataSource(name="PostGIS Main", type=SourceType.POSTGIS))
    print(f"✅ Metadata Registry: Source registered with ID {src_id}")

    # Test harvesting (mocked in registry)
    await meta_reg.harvest_source(src_id)
    tables = meta_reg.list_tables(src_id)
    print(f"✅ Metadata Registry: Harvested {len(tables)} tables")

    print("\n🚀 ALL ARCHITECTURAL MODULES VERIFIED (SMOKE TEST PASSED)!")

if __name__ == "__main__":
    try:
        asyncio.run(run_smoke_test())
    except Exception as e:
        print(f"❌ Smoke test FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
