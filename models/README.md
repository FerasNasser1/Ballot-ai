# Models

Put the trained bidding model here as `mushtra_model.pkl` (a scikit-learn
classifier saved with `joblib.dump`).

It must accept the feature vector `[sun_points, hokom_points, cards_matching_ground_suit]`
computed from a five-card hand and the ground card, and predict one of
`"Suna"` / `"Sun"`, `"Hokom"` or `"Pass"`.

If the file is missing, the game uses a hand-strength heuristic instead.
Only load model files you trust: unpickling can run arbitrary code.
