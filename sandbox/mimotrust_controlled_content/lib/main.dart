import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'models/sandbox_content.dart';
import 'pages/video_content_page.dart';
import 'services/content_repository.dart';

typedef FeaturedVideoLoader = Future<VideoContent> Function();
typedef VideoFeedLoader = Future<List<VideoContent>> Function();
typedef ContentFeedLoader = Future<List<SandboxContent>> Function();

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
  runApp(const MiMoTrustApp());
}

class MiMoTrustApp extends StatelessWidget {
  const MiMoTrustApp({
    super.key,
    this.loadVideoFeed,
    this.loadFeaturedVideo,
    this.loadContentFeed,
    this.videoBuilder,
  });

  final VideoFeedLoader? loadVideoFeed;
  final FeaturedVideoLoader? loadFeaturedVideo;
  final ContentFeedLoader? loadContentFeed;
  final VideoPageBuilder? videoBuilder;

  @override
  Widget build(BuildContext context) {
    final repository = ContentRepository();
    return MaterialApp(
      title: 'MiMoTrust',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        colorScheme: const ColorScheme.dark(
          primary: Color(0xFFFF5A5F),
          secondary: Color(0xFF4BC0C8),
          surface: Color(0xFF111111),
          error: Color(0xFFFFB35C),
        ),
        scaffoldBackgroundColor: Colors.black,
        useMaterial3: true,
      ),
      home: VideoContentPage(
        loadContents: () async {
          if (loadContentFeed != null) {
            return loadContentFeed!();
          }
          if (loadVideoFeed != null) {
            return loadVideoFeed!();
          }
          if (loadFeaturedVideo != null) {
            return <VideoContent>[await loadFeaturedVideo!()];
          }
          return repository.loadContentFeed();
        },
        videoBuilder: videoBuilder,
      ),
    );
  }
}
