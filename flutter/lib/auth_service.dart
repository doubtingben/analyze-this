import 'dart:async';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

class AuthService {
  // Web Client ID for backend verification (serverClientId)
  static const String _serverClientId = "106064975526-5cirithftrku0j78rs8h9l34p7lf84kk.apps.googleusercontent.com";
  // iOS Client ID for native Google Sign-In configuration.
  static const String _iosClientId = "106064975526-e5hbqil9s5dd02vt8lld9mrh0snpajuv.apps.googleusercontent.com";
  
  final GoogleSignIn _googleSignIn = GoogleSignIn(
    clientId: defaultTargetPlatform == TargetPlatform.iOS ? _iosClientId : null,
    serverClientId: _serverClientId,
  );
  
  // ignore: unused_field
  final FlutterSecureStorage _storage = const FlutterSecureStorage();
  static const String _storageKey = 'auth_user';

  Future<void> init() async {
    // For iOS, the clientId is read from GoogleService-Info.plist.
    // No explicit initialization needed for google_sign_in package v6+
  }

  Future<GoogleSignInAccount?> signIn() async {
    try {
      // signIn() initiates the interactive sign-in process
      final result = await _googleSignIn.signIn();
      if (result != null) {
        await _saveUser(result);
      }
      return result;
    } catch (error) {
      print('Google Sign In Error: $error');
      return null;
    }
  }

  Future<void> signOut() async {
    await _googleSignIn.signOut();
    await _storage.delete(key: _storageKey);
  }

  Future<GoogleSignInAccount?> getCurrentUser() async {
    // signInSilently replaces attemptLightweightAuthentication for restoring session
    return await _googleSignIn.signInSilently();
  }

  Future<void> _saveUser(GoogleSignInAccount user) async {
    // Placeholder for saving user data/tokens
  }
}
