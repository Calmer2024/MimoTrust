import 'package:uuid/uuid.dart';

import '../models/content_context.dart';
import '../models/sandbox_content.dart';
import 'content_grant_client.dart';
import 'context_transport.dart';

class ContextDispatcher {
  ContextDispatcher(
    this._grantClient, {
    this._transport = const MethodChannelContextTransport(),
    DateTime Function()? clock,
    String Function()? eventIdGenerator,
  }) : _clock = clock ?? DateTime.now,
       _eventIdGenerator = eventIdGenerator ?? const Uuid().v4;

  final ContentGrantClient _grantClient;
  final ContextTransport _transport;
  final DateTime Function() _clock;
  final String Function() _eventIdGenerator;

  Future<ContentContext> dispatchVideoContext({
    required ContextTrigger trigger,
    required VideoContent content,
    required MediaViewState viewState,
    DateTime? observedAt,
  }) async {
    return dispatchContext(
      trigger: trigger,
      content: content,
      viewState: viewState,
      observedAt: observedAt,
    );
  }

  Future<ContentContext> dispatchContext({
    required ContextTrigger trigger,
    required SandboxContent content,
    required ContentViewState viewState,
    DateTime? observedAt,
  }) async {
    final observation = (observedAt ?? _clock()).toUtc();
    final reference = ContentReference(
      contentType: content.contentType,
      contentId: content.id,
      contentVersion: content.version,
      contentHash: content.hash,
      canonicalUrl: content.canonicalUrl,
    );
    final grant = await _grantClient.issueGrant(reference);
    final context = ContentContext(
      eventId: _eventIdGenerator(),
      trigger: trigger,
      grant: grant,
      viewState: viewState,
      observedAt: observation,
    );
    await _transport.send(context);
    return context;
  }

  void close() {
    _grantClient.close();
  }
}
