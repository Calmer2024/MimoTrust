import 'package:flutter_test/flutter_test.dart';
import 'package:mimotrust_controlled_content/services/playback_lifecycle_policy.dart';

void main() {
  test('preserves a resume request across repeated background callbacks', () {
    final policy = PlaybackLifecyclePolicy();

    policy.recordInterruption(wasPlaying: true);
    policy.recordInterruption(wasPlaying: false);

    expect(policy.consumeResumeRequest(), isTrue);
    expect(policy.consumeResumeRequest(), isFalse);
  });

  test('does not request resume when playback was already paused', () {
    final policy = PlaybackLifecyclePolicy();

    policy.recordInterruption(wasPlaying: false);
    policy.recordInterruption(wasPlaying: false);

    expect(policy.consumeResumeRequest(), isFalse);
  });

  test('detachment clears a pending resume request', () {
    final policy = PlaybackLifecyclePolicy();

    policy.recordInterruption(wasPlaying: true);
    policy.clear();

    expect(policy.consumeResumeRequest(), isFalse);
  });
}
