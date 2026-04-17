"""Quick smoke test for Phase 1 components."""
import os
import sys
import tempfile

# Test 1: Event Bus
from backend.events import EventBus, Event, EventType

db_path = os.path.join(tempfile.mkdtemp(), "test.db")
bus = EventBus(db_path)

received = []
bus.subscribe(EventType.USER_MESSAGE, lambda e: received.append(e))
bus.emit(Event(type=EventType.USER_MESSAGE, data={"msg": "hello"}, source="test"))

assert len(received) == 1
assert received[0].data["msg"] == "hello"
events = bus.get_events(EventType.USER_MESSAGE)
assert len(events) == 1
print("1. Event bus: PASS")

# Test 2: NER extraction
from backend.memory.relational import extract_entities

ents = extract_entities("My sister Priya works in Mumbai")
types = {e["type"] for e in ents}
assert "person" in types
print(f"2. NER extraction: PASS ({len(ents)} entities)")

# Test 3: Knowledge Graph
from backend.memory.relational import KnowledgeGraph

graph_db = os.path.join(tempfile.mkdtemp(), "graph.db")
g = KnowledgeGraph(graph_db)
g.add_entity("person", "Priya", {"relationship_to_user": "sister"})
g.add_entity("place", "Mumbai")
g.add_relationship("person", "Priya", "place", "Mumbai", "LOCATED_AT")
assert g.node_count() == 2
assert g.edge_count() == 1
results = g.search("Priya")
assert len(results) > 0
print(f"3. Knowledge graph: PASS ({g.node_count()} nodes, {g.edge_count()} edges)")

# Test 4: Database conversation persistence
from backend.services.database import DatabaseService
from pathlib import Path

test_db = os.path.join(tempfile.mkdtemp(), "test.db")
db = DatabaseService(Path(test_db))
db.initialize()

session_id = db.create_session()
db.store_message(session_id, "user", "Hello ANANDI")
db.store_message(session_id, "assistant", "Hello! How can I help?")
msgs = db.get_session_messages(session_id)
assert len(msgs) == 2
assert msgs[0]["role"] == "user"
recent = db.get_recent_messages(limit=5)
assert len(recent) == 2

unembedded = db.get_unembedded_messages()
assert len(unembedded) == 2
db.mark_messages_embedded([m["id"] for m in unembedded])
unembedded2 = db.get_unembedded_messages()
assert len(unembedded2) == 0
print("4. Conversation persistence: PASS")

# Test 5: Context Engine (without memory)
from backend.context.context_engine import ContextEngine

ctx = ContextEngine()
messages = ctx.build_messages("What's on my schedule?", {
    "stats": {"water": 3, "breaks": 1, "sleep": 7},
    "schedule": [{"time": "10:00", "title": "Team standup"}],
    "habits": [{"name": "Walk", "completed": True, "streak": 5}],
    "profile": {"displayName": "Sneh", "coachingStyle": "balanced"},
})
assert messages[0]["role"] == "system"
assert "ANANDI" in messages[0]["content"]
assert messages[-1]["role"] == "user"
assert messages[-1]["content"] == "What's on my schedule?"
# Hot context should be in there
hot = [m for m in messages if "Real-time context" in m.get("content", "")]
assert len(hot) == 1
print("5. Context engine: PASS")

print("\nAll Phase 1 smoke tests passed!")
