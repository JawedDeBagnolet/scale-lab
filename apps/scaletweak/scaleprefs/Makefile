ARCHS = arm64
ROOTLESS = 1
TARGET := iphone:clang:latest:15.0

include $(THEOS)/makefiles/common.mk

BUNDLE_NAME = ScalePrefs

ScalePrefs_FILES = ScalePrefsRootListController.m ScalePrefsContainerListController.m
ScalePrefs_FRAMEWORKS = UIKit
ScalePrefs_LDFLAGS = -F$(THEOS)/sdks/iPhoneOS16.5.sdk/System/Library/PrivateFrameworks -framework Preferences
ScalePrefs_INSTALL_PATH = /Library/PreferenceBundles
ScalePrefs_CFLAGS = -fobjc-arc -Wno-deprecated-declarations

include $(THEOS_MAKE_PATH)/bundle.mk
