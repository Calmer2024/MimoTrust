import 'package:flutter/services.dart';

import '../models/content_context.dart';

abstract interface class ContextTransport {
  Future<void> send(ContentContext context);
}

class MethodChannelContextTransport implements ContextTransport {
  const MethodChannelContextTransport();

  static const channelName = 'com.mimotrust.controlledcontent/context';
  static const methodName = 'sendContentContext';
  static const requestMethodName = 'requestCurrentContentContext';
  static const MethodChannel _channel = MethodChannel(channelName);

  @override
  Future<void> send(ContentContext context) {
    return _channel.invokeMethod<void>(methodName, context.toJsonString());
  }
}

typedef GuardianContextRequestHandler = Future<void> Function(String requestId);

class GuardianRequestBridge {
  GuardianRequestBridge._();

  static final List<GuardianContextRequestHandler> _activeHandlers =
      <GuardianContextRequestHandler>[];

  static void activate(GuardianContextRequestHandler handler) {
    _activeHandlers.remove(handler);
    _activeHandlers.add(handler);
    MethodChannelContextTransport._channel.setMethodCallHandler(_handleCall);
  }

  static void deactivate(GuardianContextRequestHandler handler) {
    _activeHandlers.remove(handler);
    if (_activeHandlers.isEmpty) {
      MethodChannelContextTransport._channel.setMethodCallHandler(null);
    }
  }

  static Future<void> _handleCall(MethodCall call) async {
    if (call.method != MethodChannelContextTransport.requestMethodName) {
      throw MissingPluginException('Unsupported method ${call.method}');
    }
    final requestId = call.arguments;
    final active = _activeHandlers.lastOrNull;
    if (requestId is! String || requestId.isEmpty || active == null) {
      throw PlatformException(code: 'NO_ACTIVE_CONTENT');
    }
    await active(requestId);
  }
}
