import 'package:flutter/services.dart';

import '../models/content_context.dart';

abstract interface class ContextTransport {
  Future<void> send(ContentContext context);
}

class MethodChannelContextTransport implements ContextTransport {
  const MethodChannelContextTransport();

  static const channelName = 'com.mimotrust.controlledcontent/context';
  static const methodName = 'sendContentContext';
  static const MethodChannel _channel = MethodChannel(channelName);

  @override
  Future<void> send(ContentContext context) {
    return _channel.invokeMethod<void>(methodName, context.toJsonString());
  }
}
