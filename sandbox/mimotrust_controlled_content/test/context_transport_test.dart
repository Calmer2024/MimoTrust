import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mimotrust_controlled_content/models/content_context.dart';
import 'package:mimotrust_controlled_content/services/context_transport.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  const channel = MethodChannel(MethodChannelContextTransport.channelName);

  tearDown(() async {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(channel, null);
  });

  test(
    'sends one serialized Context through the fixed internal bridge',
    () async {
      MethodCall? received;
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            received = call;
            return null;
          });
      final context = _contextFixture();

      await const MethodChannelContextTransport().send(context);

      expect(received?.method, MethodChannelContextTransport.methodName);
      expect(received?.arguments, isA<String>());
      expect(jsonDecode(received!.arguments as String), context.toJson());
      expect(
        utf8.encode(received!.arguments as String).length,
        lessThanOrEqualTo(32 * 1024),
      );
    },
  );

  test(
    'reports a platform bridge failure to the non-blocking UI caller',
    () async {
      TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
          .setMockMethodCallHandler(channel, (call) async {
            throw PlatformException(code: 'BROADCAST_FAILED');
          });

      await expectLater(
        const MethodChannelContextTransport().send(_contextFixture()),
        throwsA(isA<PlatformException>()),
      );
    },
  );
}

ContentContext _contextFixture() {
  final observedAt = DateTime.utc(2026, 8, 2, 8);
  return ContentContext(
    eventId: '2ce1c877-0245-4c31-9fd8-a39bd76900d1',
    trigger: ContextTrigger.guardianRequest,
    grant: ContentGrant(
      grantCode: 'one-time-code',
      expiresAt: observedAt.add(const Duration(minutes: 3)),
      audience: 'mimotrust_guardian_backend',
      scopes: const <String>['manifest:read', 'asset:read'],
      exchangeUrl: Uri.parse('http://127.0.0.1:8787/v1/grants/exchange'),
      contentReference: ContentReference(
        contentType: 'video',
        contentId: 'video-001',
        contentVersion: 'v1',
        contentHash: List.filled(64, '0').join(),
        canonicalUrl: Uri.parse(
          'https://sandbox.mimotrust.local/content/video-001',
        ),
      ),
    ),
    viewState: MediaViewState(
      positionMs: 3500,
      durationMs: 22467,
      isPlaying: true,
    ),
    observedAt: observedAt,
  );
}
