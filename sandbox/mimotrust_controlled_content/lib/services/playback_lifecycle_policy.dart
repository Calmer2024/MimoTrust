class PlaybackLifecyclePolicy {
  bool _resumeOnForeground = false;

  void recordInterruption({required bool wasPlaying}) {
    _resumeOnForeground = _resumeOnForeground || wasPlaying;
  }

  bool consumeResumeRequest() {
    final shouldResume = _resumeOnForeground;
    _resumeOnForeground = false;
    return shouldResume;
  }

  void clear() {
    _resumeOnForeground = false;
  }
}
