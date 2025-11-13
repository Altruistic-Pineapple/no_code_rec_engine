import os

mix_id = "3aff39a1-c235-443d-8d2f-27efad650cde"
print("CSV exists:", os.path.exists(f"uploads/{mix_id}.csv"))
print("Mapping exists:", os.path.exists(f"mappings/{mix_id}.json"))
