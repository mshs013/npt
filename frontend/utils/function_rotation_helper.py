from itertools import groupby
from operator import itemgetter
from collections import defaultdict
from datetime import datetime, date, time, timedelta
from django.db.models import QuerySet, Q
def calculate_npt_minutes(shift_start, shift_end, npt_qs):
    """
    Calculates the total NPT in minutes that falls within a given time window (shift).

    Args:
        shift_start (datetime): The start time of the shift instance.
        shift_end (datetime): The end time of the shift instance.
        npt_qs (QuerySet): The pre-filtered QuerySet of ProcessedNPT objects.

    Returns:
        float: The total non-productive time in minutes.
    """
    total_npt_seconds = 0

    shift_npt_qs = npt_qs.filter(
        off_time__lt=shift_end
    ).filter(
        Q(on_time__gte=shift_start) | Q(on_time__isnull=True)
    )

    for npt in shift_npt_qs:
        # If on_time is null, the NPT period is ongoing.
        # We consider it to last until the end of the current shift window.
        npt_end = npt.on_time if npt.on_time else shift_end

        # Determine the actual overlap period by finding the intersection
        # between the NPT period and the shift period.
        overlap_start = max(npt.off_time, shift_start)
        overlap_end = min(npt_end, shift_end)

        # Calculate the duration of the overlap in seconds if it's a valid period
        if overlap_end > overlap_start:
            duration_seconds = (overlap_end - overlap_start).total_seconds()
            total_npt_seconds += duration_seconds
    
    return total_npt_seconds / 60.0


def generate_shift_blocks(shift_start, shift_end, base_date, num_blocks=4):
    """
    Generate shift blocks for a specific date
    
    Args:
        shift_start: time object (e.g., time(6, 0))
        shift_end: time object (e.g., time(14, 0))
        base_date: date object for this shift instance
        num_blocks: number of blocks to create
    """
    shift_start_dt = datetime.combine(base_date, shift_start)
    shift_end_dt = datetime.combine(base_date, shift_end)
    
    # Handle overnight shift
    if shift_end_dt <= shift_start_dt:
        shift_end_dt += timedelta(days=1)
    
    blocks = []
    for i in range(num_blocks):
        if i == 0:
            block_start = shift_start_dt
            block_end = shift_start_dt + timedelta(hours=2)
            blocks.append((block_start, block_end))
        elif num_blocks - i == 1:
            block_start = shift_start_dt + timedelta(hours=2*i)
            block_end = shift_end_dt
            blocks.append((block_start, block_end))
        else:
            block_start = shift_start_dt + timedelta(hours=2*i)
            block_end = block_start + timedelta(hours=2)
            blocks.append((block_start, block_end))
    
    return blocks

def split_records_by_blocks_multi_day(rotation_qs, shift, from_datetime, to_datetime, num_blocks=4):
    """
    Split rotation records into shift blocks across multiple days
    
    Args:
        rotation_qs: QuerySet of RotationStatus objects
        shift: Shift object with start_time and end_time
        from_datetime: datetime start of range
        to_datetime: datetime end of range
        num_blocks: number of blocks per shift
    
    Returns:
        List of dictionaries with shift instances and their blocks
    """
    all_shift_results = []
    
    # Generate all dates in the range
    current_date = from_datetime.date()
    end_date = to_datetime.date()
    
    while current_date <= end_date:
        # Create shift datetime for this date
        shift_start_dt = datetime.combine(current_date, shift.start_time)
        shift_end_dt = datetime.combine(current_date, shift.end_time)
        
        # Handle overnight shifts
        if shift.start_time > shift.end_time:
            shift_end_dt += timedelta(days=1)
        
        # Check if this shift instance overlaps with our date range
        if shift_start_dt < to_datetime and shift_end_dt > from_datetime:
            # Clip to the actual date range
            effective_start = max(shift_start_dt, from_datetime)
            effective_end = min(shift_end_dt, to_datetime)
            
            # print(f"\n--- Processing {shift.name} for {current_date} ---")
            # print(f"Shift time: {shift_start_dt} to {shift_end_dt}")
            # print(f"Effective time: {effective_start} to {effective_end}")
            
            # Generate blocks for this shift instance
            blocks = generate_shift_blocks(shift.start_time, shift.end_time, current_date, num_blocks)
            
            # Filter rotation records for this shift instance
            shift_records = [r for r in rotation_qs 
                           if effective_start <= r.count_time <= effective_end]
            
            if shift_records:
                # Process blocks for this shift instance
                block_results = split_records_by_blocks_single_shift(
                    shift_records, blocks, shift.name, current_date
                )
                
                all_shift_results.append({
                    'shift_name': shift.name,
                    'shift_date': current_date,
                    'shift_key': f"{shift.name} {current_date.strftime('%Y-%m-%d')}",
                    'blocks': block_results,
                    'effective_start': effective_start,
                    'effective_end': effective_end
                })
            # else:
            #     print(f"No records found for {shift.name} on {current_date}")
        
        current_date += timedelta(days=1)
    
    return all_shift_results

def split_records_by_blocks_single_shift(shift_records, blocks, shift_name, shift_date):
    """
    Process records for a single shift instance
    """
    block_results = []
    
    for block_start, block_end in blocks:
        block_records = [r for r in shift_records if block_start <= r.count_time < block_end]
        
        if not block_records:
            block_results.append({
                'block_start': block_start,
                'block_end': block_end,
                'total_count': 0
            })
            continue
        
        total_count = 0
        segment_start_count = block_records[0].count
        
        print(f"Block {block_start.strftime('%H:%M')} - {block_end.strftime('%H:%M')}")
        print(f"Initial: {segment_start_count}")
        
        for i in range(1, len(block_records)):
            current_record = block_records[i]
            previous_record = block_records[i-1]
            
            if current_record.count < previous_record.count:
                decrease_amount = previous_record.count - current_record.count + 1
                RESET_THRESHOLD = 1
                
                if decrease_amount > RESET_THRESHOLD:
                    segment_count = previous_record.count - segment_start_count + 1
                    total_count += segment_count
                    # print(f"Reset detected: {previous_record.count} → {current_record.count}")
                    # print(f"Adding segment: {previous_record.count} - {segment_start_count} = {segment_count}")
                    
                    segment_start_count = current_record.count
                # else:
                #     print(f"Small decrease (not reset): {previous_record.count} → {current_record.count}")
        
        # Always add the final segment
        if block_records:
            final_segment = block_records[-1].count - segment_start_count + 1
            total_count += final_segment
            # print(f"Final segment: {block_records[-1].count} - {segment_start_count} = {final_segment}")
            # print(f"Block total: {total_count}")
        
        block_results.append({
            'block_start': block_start,
            'block_end': block_end,
            'total_count': total_count
        })
    
    return block_results