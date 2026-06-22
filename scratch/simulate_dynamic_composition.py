def simulate_step(status_dict):
    # Database breakdown
    avg_clean = 1.35
    avg_whitespace = 70.64
    avg_faded = 25.67
    avg_logo = 0.0
    avg_stamp = 0.0
    avg_handwritten = 0.0
    avg_noise = 1.06
    
    # 10 Faded snippets with 2.5% impact each
    snippets = []
    for i in range(10):
        snippets.append({
            "type": "faded_text",
            "impact": 2.5,
            "status": status_dict.get(f"faded_{i}", "pending")
        })
        
    # Calculate counts and impact sums
    pending_counts = {}
    pending_impacts = {}
    accepted_impact_total = 0.0
    
    for s in snippets:
        t = s["type"]
        status = s["status"]
        impact = s["impact"]
        if status == "pending":
            pending_counts[t] = pending_counts.get(t, 0) + 1
            pending_impacts[t] = pending_impacts.get(t, 0.0) + impact
        elif status == "accepted":
            accepted_impact_total += impact
            
    # Configuration
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
    
    # Apply dynamic calculations
    # 1. Clean value is baseline clean text + all accepted snippet impacts
    segment_cfg["clean"]["value"] += accepted_impact_total
    
    # 2. Anomaly categories use the pending snippet impact sum if they have pending snippets
    for key in ["faded", "logo", "stamp", "handwritten", "noise"]:
        cfg = segment_cfg[key]
        snippet_pending_sum = 0.0
        has_snippets = False
        
        if "snippet_key" in cfg:
            snippet_pending_sum += pending_impacts.get(cfg["snippet_key"], 0.0)
            if cfg["snippet_key"] in pending_counts or cfg["snippet_key"] in [s["type"] for s in snippets]:
                has_snippets = True
        if "extra_snippet_key" in cfg:
            snippet_pending_sum += pending_impacts.get(cfg["extra_snippet_key"], 0.0)
            if cfg["extra_snippet_key"] in pending_counts or cfg["extra_snippet_key"] in [s["type"] for s in snippets]:
                has_snippets = True
                
        if has_snippets:
            cfg["value"] = snippet_pending_sum
            
    # Normalize to 100%
    total_val_sum = sum(cfg["value"] for cfg in segment_cfg.values())
    if total_val_sum > 0:
        scale = 100.0 / total_val_sum
        for cfg in segment_cfg.values():
            cfg["value"] *= scale
            
    print("\nState Summary:")
    print(f"  Accepted total: {accepted_impact_total:.2f}% | Pending total: {sum(pending_impacts.values()):.2f}%")
    sum_normalized = 0.0
    for key, cfg in segment_cfg.items():
        val = cfg["value"]
        sum_normalized += val
        lbl = cfg["label"]
        count = 0
        if "snippet_key" in cfg:
            count += pending_counts.get(cfg["snippet_key"], 0)
        if "extra_snippet_key" in cfg:
            count += pending_counts.get(cfg["extra_snippet_key"], 0)
        if count > 0:
            lbl = f"{lbl} ({count})"
        print(f"    {lbl}: {val:.2f}%")
    print(f"  Sum: {sum_normalized:.2f}%")

def main():
    print("--- STEP 1: All 10 snippets pending ---")
    simulate_step({})
    
    print("\n--- STEP 2: 4 snippets accepted ---")
    simulate_step({f"faded_{i}": "accepted" for i in range(4)})
    
    print("\n--- STEP 3: All 10 snippets accepted ---")
    simulate_step({f"faded_{i}": "accepted" for i in range(10)})

if __name__ == "__main__":
    main()
