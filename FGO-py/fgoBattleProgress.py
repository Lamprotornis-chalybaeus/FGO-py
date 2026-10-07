"""Bounded battle liveness; sampled pixels stay in memory and never authorize input."""
import hashlib,time


class BattleProgressTracker:
    def __init__(self,*,clock=time.monotonic,stall_timeout=60,phase_hard_timeout=180):
        self.clock=clock;self.stall_timeout=stall_timeout;self.phase_hard_timeout=phase_hard_timeout
        self.turn_number=0;self.phase='WAIT_TURN_BEGIN'
        self.phase_started=self.last_meaningful_progress=clock()
        self.last_state=None;self.last_positive_state=None;self.last_capture_sequence=None
        self.last_visual_signature=None;self.last_loading_signature=None
        self.mean_brightness=None;self.sampled_mean_delta=None;self._visual=None

    def progress(self,reason):
        self.last_meaningful_progress=self.clock()
        return reason

    def mark_turn_begin(self,turn):
        self.turn_number=turn;self.phase='TURN_INPUT';self.phase_started=self.clock()
        return self.progress(f'turn_{turn}_begin')

    def mark_turn_input_complete(self,turn):
        self.turn_number=turn;self.phase='WAIT_NEXT_TURN';self.phase_started=self.clock()
        return self.progress(f'turn_{turn}_inputs_complete')

    def _visual_progress(self,detect):
        image=getattr(detect,'im',None)
        if getattr(image,'shape',None)!=(720,1280,3):return False
        import numpy as np
        # Battlefield only: omit static HUD, Attack button and card/skill rows.
        sample=image[90:560:12,100:1120:12].astype(np.int16)
        self.mean_brightness=float(sample.mean())
        self.last_visual_signature=hashlib.sha256(sample.tobytes()).digest()[:8]
        changed=False
        if self._visual is not None:
            delta=np.abs(sample-self._visual)
            self.sampled_mean_delta=float(delta.mean())
            changed=self.sampled_mean_delta>=3 and float((delta.mean(axis=2)>=12).mean())>=.08
        # Compare against the last accepted sample, so gradual motion can
        # accumulate; tiny raster noise alone cannot refresh the stall clock.
        if self._visual is None or changed:self._visual=sample
        return changed

    def observe(self,observation,detect):
        sequence=observation.capture_sequence
        if sequence is None or self.last_capture_sequence is not None and sequence<=self.last_capture_sequence:return None
        self.last_capture_sequence=sequence
        state=getattr(observation.state,'name',str(observation.state))
        previous=self.last_state;self.last_state=state
        visual=self._visual_progress(detect)
        if state not in {'UNKNOWN','LOADING','TURN_BEGIN','BATTLE_RESULT','DEFEATED'}:return None
        if state!='UNKNOWN':self.last_positive_state=state
        loading=None
        if state=='LOADING':loading=getattr(detect,'getLoadingProgressSignature',lambda:None)()
        loading_changed=loading is not None and loading!=self.last_loading_signature
        self.last_loading_signature=loading
        if state!=previous:return self.progress(f'{previous or "INITIAL"} -> {state}')
        if state=='LOADING' and loading_changed:return self.progress('loading_progress')
        if state=='UNKNOWN' and visual:return self.progress('unknown_visual_progress')
        return None

    def stalled(self):return self.clock()-self.last_meaningful_progress>=self.stall_timeout
    def hard_expired(self):return self.clock()-self.phase_started>=self.phase_hard_timeout
    def snapshot(self):
        now=self.clock()
        return dict(turn=self.turn_number,phase=self.phase,last_positive_state=self.last_positive_state,
                    last_meaningful_progress=self.last_meaningful_progress,
                    elapsed_since_progress=max(0,now-self.last_meaningful_progress),
                    elapsed_since_turn_input=max(0,now-self.phase_started))
