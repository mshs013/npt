import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, time

# ==============================================================================
# Helper Function to Process NPT into Hourly Buckets
# ==============================================================================
def process_npt_to_hourly(npt_df: pd.DataFrame) -> pd.DataFrame:
    """
    Processes raw NPT data to calculate total NPT for each hour of the day.

    This function distributes NPT durations across hour boundaries and caps
    the total NPT for any given hour at 3600 seconds (1 hour).

    Args:
        npt_df: DataFrame containing NPT events with 'machine_label',
                'off_time', and 'on_time'.

    Returns:
        A DataFrame with columns ['machine_label', 'hour', 'npt_seconds'].
    """
    if npt_df.empty:
        return pd.DataFrame(columns=['machine_label', 'hour', 'npt_seconds'])

    # Use a timezone-aware 'now' for ongoing NPT events to prevent errors
    if npt_df['off_time'].dt.tz is not None:
        now = pd.Timestamp.now(tz=npt_df['off_time'].dt.tz)
    else:
        # Fallback for timezone-naive datetimes
        now = pd.Timestamp.now()
        
    npt_df['on_time'] = npt_df['on_time'].fillna(now)

    # Initialize a dictionary to hold hourly NPT data for each machine
    unique_machines = npt_df['machine_label'].unique()
    hourly_npt_data = {mc: np.zeros(24) for mc in unique_machines}

    # Iterate over each NPT event to distribute its duration
    for _, row in npt_df.iterrows():
        machine = row['machine_label']
        start_time = row['off_time']
        end_time = row['on_time']
        
        current_time = start_time
        while current_time < end_time:
            hour_index = current_time.hour
            
            # Find the end of the current hour, which is the start of the next one
            end_of_hour = (current_time + pd.Timedelta(hours=1)).replace(
                minute=0, second=0, microsecond=0
            )
            
            # The NPT chunk for this hour ends at either the event's actual
            # end time or the end of the hour, whichever comes first.
            chunk_end_time = min(end_time, end_of_hour)
            
            duration_seconds = (chunk_end_time - current_time).total_seconds()
            
            # Add the calculated duration to the correct hourly bucket
            hourly_npt_data[machine][hour_index] += duration_seconds
            
            # Move the time cursor forward
            current_time = chunk_end_time
            
    # Convert the dictionary into a long-format DataFrame for easy plotting
    processed_data = []
    for machine, hourly_values in hourly_npt_data.items():
        for hour, npt_seconds in enumerate(hourly_values):
            processed_data.append({
                'machine_label': machine,
                'hour': hour,
                'npt_seconds': min(npt_seconds, 3600)  # Cap NPT at 1 hour
            })
            
    return pd.DataFrame(processed_data)
