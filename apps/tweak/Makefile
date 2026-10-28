ARCHS = arm64
ROOTLESS = 1
TARGET := iphone:clang:latest:15.0
INSTALL_TARGET_PROCESSES = Instagram

include $(THEOS)/makefiles/common.mk

TWEAK_NAME = ScaleTweak

ScaleTweak_FILES = Tweak.x ScaleContainerManager.m fishhook.c
ScaleTweak_CFLAGS = -fobjc-arc -Wno-unused-variable -Wno-deprecated-declarations -Wno-unused-function -Wno-unused-variable -Wno-deprecated-declarations -Wno-unused-function -Wno-unused-variable -Wno-deprecated-declarations -Wno-unused-function -Wno-unused-variable -Wno-deprecated-declarations -Wno-unused-variable -Wno-deprecated-declarations
ScaleTweak_FRAMEWORKS = UIKit Foundation Security SystemConfiguration
ScaleTweak_PRIVATE_FRAMEWORKS = IOKit
ScaleTweak_LDFLAGS = -framework IOKit -framework SystemConfiguration

include $(THEOS_MAKE_PATH)/tweak.mk

SUBPROJECTS += scalectl
include $(THEOS_MAKE_PATH)/aggregate.mk
