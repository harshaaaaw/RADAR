def simulate():
    # Database breakdown for DOC-20260617-01BC
    avg_clean = 0.0
    avg_whitespace = 28.04
    avg_faded = 0.0
    avg_logo = 67.92
    avg_stamp = 0.0
    avg_handwritten = 0.0
    avg_noise = 0.72
    
    # Snippet impacts
    pending_snippets = [
        {"type": "signature", "impact": 0.39},
        {"type": "stamp", "impact": 0.23},
        # 23 faded_text snippets
        *([{"type": "faded_text", "impact": 0.5}] * 23)
    ]
    
    counts = {}
    snippet_impacts = {}
    for s in pending_snippets:
        t = s["type"]
        counts[t] = counts.get(t, 0) + 1
        snippet_impacts[t] = snippet_impacts.get(t, 0.0) + s["impact"]
        
    segment_cfg = {
        "clean": {"label": "Extractable Text", "value": avg_clean},
        "whitespace": {"label": "Whitespace", "value": avg_whitespace},
        "faded": {"label": "Faded Text", "value": avg_faded, "snippet_key": "faded_text"},
        "logo": {"label": "Logo/Image", "value": avg_logo, "snippet_key": "logo"},
        "stamp": {"label": "Stamp", "value": avg_stamp, "snippet_key": "stamp"},
        "handwritten": {
            "label": "Handwritten",
            "value": avg_handwritten,
            "snippet_key": "handwritten",
            "extra_snippet_key": "signature"
        },
        "noise": {"label": "Noise", "value": avg_noise, "snippet_key": "text_anomaly"}, 
    }
    
    for key, cfg in segment_cfg.items():
        snippet_sum = 0.0
        if "snippet_key" in cfg:
            snippet_sum += snippet_impacts.get(cfg["snippet_key"], 0.0)
        if "extra_snippet_key" in cfg:
            snippet_sum += snippet_impacts.get(cfg["extra_snippet_key"], 0.0)
            
        cfg["value"] = max(cfg["value"], snippet_sum)
        
    total_val_sum = sum(cfg["value"] for cfg in segment_cfg.values())
    print("Total Sum before normalization:", total_val_sum)
    
    if total_val_sum > 0:
        scale = 100.0 / total_val_sum
        for cfg in segment_cfg.values():
            cfg["value"] *= scale
            
    print("Normalized values:")
    for key, cfg in segment_cfg.items():
        lbl = cfg["label"]
        count = 0
        if "snippet_key" in cfg:
            count += counts.get(cfg["snippet_key"], 0)
        if "extra_snippet_key" in cfg:
            count += counts.get(cfg["extra_snippet_key"], 0)
        if count > 0:
            lbl = f"{lbl} ({count})"
        print(f"  {lbl}: {cfg['value']:.2f}%")

if __name__ == "__main__":
    simulate()
