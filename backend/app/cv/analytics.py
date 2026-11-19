"""Aggregate persisted frame annotations without conflating occupancy and visitors."""
import numpy as np


def summarize_frames(frames):
    if not frames:
        return {"samples":0,"groups":[]}
    counts=[f['crowd_count'] for f in frames]
    durations=[max(0.,min(f.get('valid_until',f['timestamp']),
                    frames[i+1]['timestamp'] if i+1<len(frames) else float('inf'))-f['timestamp'])
               for i,f in enumerate(frames)]
    groups={}
    for f in frames:
        for g in f['groups']:
            row=groups.setdefault(g['group_id'],dict(group_id=g['group_id'],first_seen=f['timestamp'],
                last_seen=f['timestamp'],observations=0,speeds=[],member_counts=[]))
            row['last_seen']=f['timestamp'];row['observations']+=1
            row['member_counts'].append(g['member_count'])
            if g['motion_speed'] is not None:
                row['speeds'].append(g['motion_speed'])
    for row in groups.values():
        speeds=row.pop('speeds')
        row['mean_speed_px_s']=float(np.mean(speeds)) if speeds else None
        values=row.pop('member_counts');row['min_members']=min(values);row['max_members']=max(values)
    return dict(samples=len(frames),first_timestamp=frames[0]['timestamp'],last_timestamp=frames[-1]['timestamp'],
        min_count=min(counts),peak_count=max(counts),mean_count=float(np.average(counts,weights=durations))
        if sum(durations)>0 else float(np.mean(counts)),count_semantics='visible occupancy, not unique visitors',
        groups=list(groups.values()))
