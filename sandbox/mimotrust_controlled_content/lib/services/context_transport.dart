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

  static GuardianContextRequestHandler? _activeHandler;

  static void activate(GuardianContextRequestHandler handler) {
    _activeHandler = handler;
    MethodChannelContextTransport._channel.setMethodCallHandler((call) async {
      if (call.method != MethodChannelContextTransport.requestMethodName) {
        throw MissingPluginException('Unsupported method ${call.method}');
      }
      final requestId = call.arguments;
      final active = _activeHandler;
      if (requestId is! String || requestId.isEmpty || active == null) {
        throw PlatformException(code: 'NO_ACTIVE_CONTENT');
      }
      await active(requestId);
    });
  }

  static void deactivate(GuardianContextRequestHandler handler) {
    if (identical(_activeHandler, handler)) {
      _activeHandler = null;
      MethodChannelContextTransport._channel.setMethodCallHandler(null);
    }
  }
}
