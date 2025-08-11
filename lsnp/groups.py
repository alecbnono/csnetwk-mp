from typing import Dict, Set, List

class GroupState:
    def __init__(self):
        # group_id -> {name, members:set}
        self.groups: Dict[str, Dict] = {}

    def create(self, group_id: str, group_name: str, members: List[str]):
        self.groups[group_id] = {"name": group_name, "members": set(members)}

    def update(self, group_id: str, add: List[str], remove: List[str]):
        g = self.groups.setdefault(group_id, {"name": group_id, "members": set()})
        for m in add: g["members"].add(m)
        for m in remove: g["members"].discard(m)

    def members(self, group_id: str) -> Set[str]:
        g = self.groups.get(group_id)
        return set(g["members"]) if g else set()

    def name_of(self, group_id: str) -> str:
        g = self.groups.get(group_id)
        return g["name"] if g else group_id
