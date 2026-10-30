"""Continue the authorized public HTML recovery queues with durable batch checkpoints."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--start-queue', choices=('tag', 'gon'), default='tag')
args = parser.parse_args()
root = Path('local/thread-audit')
work = root / 'recovery/public-dat'
queues = {'tag': work / 'embedded-tag-source-queue.json', 'gon': work / 'gon-source-queue.json'}
run_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
state_path = work / 'active-recovery-run.json'
history_path = work / ('worker-batches-' + run_id + '.json')
state = {'pid': os.getpid(), 'script': str(Path(__file__).resolve()), 'started_at': datetime.now(timezone.utc).isoformat(),
         'status': 'running', 'queue': args.start_queue, 'history': str(history_path), 'batches': 0}
history = []
phase_number = 0
zero_batches = {'tag': 0, 'gon': 0}
kind = args.start_queue


def checkpoint():
    state['updated_at'] = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    resume_path = root / 'recovery/resume-index.json'
    resume = json.loads(resume_path.read_text(encoding='utf-8'))
    resume.update(active_worker_state=str(state_path.relative_to(root)), active_worker_pid=state['pid'],
                  active_worker_script=state['script'], active_worker_status=state['status'],
                  status='worker_' + state['status'],
                  active_worker_phase=state.get('phase'),
                  next_stage='follow-active-worker-' + kind if state['status'] == 'running' else state['status'],
                  updated_at=state['updated_at'])
    resume['runner'] = ('Follow the saved active worker PID and phase; do not launch a duplicate.'
                        if state['status'] == 'running' else
                        'Inspect saved worker output and backoff, then resume scripts/continue_embedded_archive_recovery.py.')
    shared_path = work / 'embedded-http-backoff.json'
    if shared_path.exists():
        resume['next_request_after_utc'] = json.loads(shared_path.read_text(encoding='utf-8'))['next_request_after_utc']
    resume_path.write_text(json.dumps(resume, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def call(script, *arguments):
    global phase_number
    phase_number += 1
    state.update(phase=script, phase_started_at=datetime.now(timezone.utc).isoformat())
    checkpoint()
    result = subprocess.run([sys.executable, '-X', 'utf8', '-u', '-B', 'scripts/' + script, *map(str, arguments)],
                            capture_output=True, text=True, encoding='utf-8')
    output_path = work / f'worker-{run_id}-{phase_number:04d}-{Path(script).stem}.log'
    output_path.write_text(result.stdout + result.stderr, encoding='utf-8')
    state['last_output'] = str(output_path)
    if result.returncode:
        state.update(status='failed_requires_review', returncode=result.returncode)
        checkpoint()
        raise SystemExit(result.returncode)
    return result.stdout


checkpoint()
print(json.dumps(state), flush=True)
while True:
    state['queue'] = kind
    queue_path = queues[kind]
    queue = json.loads(queue_path.read_text(encoding='utf-8'))
    cached = [{'cache': source['cache'], 'source_url': source.get('resolved_url') or source['source_url'],
               **({'parent_mapping_path': queue['parent_mapping_path']} if queue.get('parent_mapping_path') else {})}
              for source in queue['sources'] if source['status'] == 'fetched_pending_merge']
    fetch_status = 'cached_pending_merge'
    if cached:
        manifest = work / f'worker-cached-{run_id}-{state["batches"]:04d}.json'
        manifest.write_text(json.dumps(cached, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    elif queue['pending'] and zero_batches[kind] < 2:
        output = call('fetch_embedded_archive_pages.py', '--queue', queue_path, '--limit', '4')
        fetched = json.loads(output.splitlines()[-1])
        fetch_status = fetched['status']
        if not fetched.get('fetched_sources'):
            if fetch_status == 'parsed_empty_page':
                zero_batches[kind] += 1
                continue
            state.update(status=fetch_status, retry_after=fetched.get('retry_after'))
            break
        manifest = Path(fetched['batch_manifest'])
    else:
        other = 'gon' if kind == 'tag' else 'tag'
        if json.loads(queues[other].read_text(encoding='utf-8'))['pending'] and zero_batches[other] < 2:
            kind = other
            continue
        state['status'] = 'cached_scopes_processed_or_zero_yield_requires_new_evidence'
        break
    new_ids = set()
    if kind == 'gon':
        mapping = json.loads(call('build_archive_parent_map.py', '--match-cached-posts'))
        new_ids.update(mapping['new_mapped_ids'])
    primary = json.loads(call('recover_embedded_archive_posts.py', '--queue', queue_path, '--manifest', manifest))
    ledgers = [primary['ledger']]
    added = primary['added_floors']
    repaired = primary.get('repaired_source_loss_floors', 0)
    mapping = json.loads(call('build_archive_parent_map.py', '--match-cached-posts'))
    new_ids.update(mapping['new_mapped_ids'])
    gon_queue = json.loads(queues['gon'].read_text(encoding='utf-8'))
    affected = [{'cache': source['cache'], 'source_url': source.get('resolved_url') or source['source_url'],
                 'parent_mapping_path': gon_queue['parent_mapping_path']}
                for source in gon_queue['sources'] if source['status'] == 'partial_parent_mapping'
                and new_ids.intersection(source.get('unmapped_tkool_dat_ids', {}))]
    if affected:
        enriched = work / f'worker-enriched-{run_id}-{state["batches"]:04d}.json'
        enriched.write_text(json.dumps(affected, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        secondary = json.loads(call('recover_embedded_archive_posts.py', '--queue', queues['gon'], '--manifest', enriched))
        ledgers.append(secondary['ledger'])
        added += secondary['added_floors']
        repaired += secondary.get('repaired_source_loss_floors', 0)
    call('refresh_thread_recovery_reports.py')
    call('audit_thread_counts.py')
    rejected_dates = [item for ledger in ledgers for source in json.loads(Path(ledger).read_text(encoding='utf-8'))
                      for thread in source['threads'] for item in thread.get('rejected', [])]
    state['batches'] += 1
    batch = {'queue': kind, 'ledgers': ledgers, 'added_floors': added, 'repaired_source_loss_floors': repaired,
             'new_parent_ids': sorted(new_ids), 'date_rejections': rejected_dates,
             'reports': json.loads((root / 'recovery/recovery-summary.json').read_text(encoding='utf-8')),
             'completed_at': datetime.now(timezone.utc).isoformat()}
    history.append(batch)
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    state['last_completed_batch'] = batch
    checkpoint()
    print(json.dumps(batch, ensure_ascii=False), flush=True)
    if rejected_dates:
        state['status'] = 'date_rejections_require_source_review'
        break
    if fetch_status not in ('cached_pending_merge', 'fetched_pending_merge', 'parsed_empty_page'):
        state['status'] = fetch_status
        break
    zero_batches[kind] = zero_batches[kind] + 1 if added == 0 and repaired == 0 else 0
state['ended_at'] = datetime.now(timezone.utc).isoformat()
checkpoint()
print(json.dumps(state, ensure_ascii=False), flush=True)
