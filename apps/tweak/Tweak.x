// ═══════════════════════════════════════════════════════════════════════
// ScaleTweak — Tweak.x v2 (corrigé)
// Corrections: JB timing, opendir, /tmp write, CNCopy, fishhook, cleanup
// ═══════════════════════════════════════════════════════════════════════

#include <CommonCrypto/CommonDigest.h>
#import <Foundation/Foundation.h>
#import "ScaleContainerManager.h"
#include "fishhook.h"
#include <stdlib.h>
#include <string.h>
#include <Security/Security.h>
#include <sys/sysctl.h>
#import <CoreTelephony/CTTelephonyNetworkInfo.h>
#import <CoreTelephony/CTCarrier.h>
#import <WebKit/WebKit.h>
#import <CoreBluetooth/CoreBluetooth.h>
#include <sys/stat.h>
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <mach/mach.h>
#include <dirent.h>
#include <ifaddrs.h>
#include <net/if.h>

// SystemConfiguration / CaptiveNetwork for BSSID
extern CFDictionaryRef CNCopyCurrentNetworkInfo(CFStringRef interfaceName) __attribute__((weak_import));
extern CFArrayRef CNCopySupportedInterfaces(void) __attribute__((weak_import));
extern NSString *const kCNNetworkInfoKeyBSSID;
extern NSString *const kCNNetworkInfoKeySSID;
extern NSString *const kCNNetworkInfoKeySSIDData;

typedef mach_port_t io_registry_entry_t;
typedef uint32_t IOOptionBits;
extern CFTypeRef IORegistryEntryCreateCFProperty(io_registry_entry_t, CFStringRef, CFAllocatorRef, IOOptionBits);

// ═══════════════════════════════════════════════════════════════════════
// MARK: — State
// ═══════════════════════════════════════════════════════════════════════

static NSString *_containerHome = nil, *_originalHome = nil, *_containerUUID = nil;
static NSString *_currentAppID = nil;
static NSString *_spoofIDFV = nil, *_spoofIDFA = nil, *_spoofSerial = nil, *_spoofPlatformUUID = nil;
static NSString *_spoofCarrierName = nil, *_spoofMCC = nil, *_spoofMNC = nil, *_spoofISOCountry = nil;
static int64_t _diskSpaceOffset = 0;
static NSString *_spoofDeviceName = nil, *_spoofHostname = nil, *_spoofWiFiMAC = nil, *_spoofBTMAC = nil;
static NSString *_spoofTimezone = nil, *_spoofLocale = nil, *_spoofUserAgent = nil;
static NSString *_spoofSSID = nil, *_spoofBSSID = nil;
static NSString *_proxyHost = nil;
static int _proxyPort = 0;
static NSString *_proxyUser = nil;
static NSString *_proxyPass = nil;
static float _spoofBattery = 0.85;
static NSString *_batteryStatePath = nil;
static NSTimeInterval _batterySessionStart = 0;
static float _batteryStartLevel = 0;
static int _bootTimeOffset = 0;
static uint32_t *_visibleMap = NULL, _visibleCount = 0;

// ═══════════════════════════════════════════════════════════════════════
// MARK: — Helpers
// ═══════════════════════════════════════════════════════════════════════

// Forward declarations
static void injectSavedCookies(void);
static float loadBatteryState(void);
static void saveBatteryState(float level);
static void startBatteryTimer(void);
static float currentBattery(void);
static void scaleLog(NSString *msg) {
    NSString *line = [NSString stringWithFormat:@"%@ %@\n", [NSDate date], msg];
    NSFileHandle *fh = [NSFileHandle fileHandleForWritingAtPath:@"/tmp/scaletw.log"];
    if (!fh) { [line writeToFile:@"/tmp/scaletw.log" atomically:YES encoding:NSUTF8StringEncoding error:nil]; }
    else { [fh seekToEndOfFile]; [fh writeData:[line dataUsingEncoding:NSUTF8StringEncoding]]; [fh closeFile]; }
}

static void hashSeed(const char *in, unsigned char *out) {
    CC_SHA256(in, (CC_LONG)strlen(in), out);
}

static NSString *dUUID(NSString *seed) {
    unsigned char h[CC_SHA256_DIGEST_LENGTH];
    hashSeed([[NSString stringWithFormat:@"%@_%@", _containerUUID, seed] UTF8String], h);
    return [NSString stringWithFormat:
        @"%02X%02X%02X%02X-%02X%02X-%02X%02X-%02X%02X-%02X%02X%02X%02X%02X%02X",
        h[0],h[1],h[2],h[3],h[4],h[5],(h[6]&0x0F)|0x40,h[7],
        (h[8]&0x3F)|0x80,h[9],h[10],h[11],h[12],h[13],h[14],h[15]];
}

static NSString *dMAC(NSString *seed) {
    unsigned char h[CC_SHA256_DIGEST_LENGTH];
    hashSeed([[NSString stringWithFormat:@"%@_%@", _containerUUID, seed] UTF8String], h);
    h[0] = (h[0] & 0xFE) | 0x02;
    return [NSString stringWithFormat:@"%02X:%02X:%02X:%02X:%02X:%02X", h[0],h[1],h[2],h[3],h[4],h[5]];
}

static NSString *dSerial(void) {
    unsigned char h[CC_SHA256_DIGEST_LENGTH];
    hashSeed([[NSString stringWithFormat:@"%@_serial", _containerUUID] UTF8String], h);
    static const char c[] = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789";
    char s[13];
    for (int i = 0; i < 12; i++) s[i] = c[h[i] % (sizeof(c) - 1)];
    s[12] = 0;
    return [NSString stringWithUTF8String:s];
}

static BOOL isJBPath(NSString *path) {
    if (!path) return NO;
    static NSArray *frags = nil;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        frags = @[@"/var/jb", @"/Applications/Cydia", @"/Applications/Sileo",
            @"/Applications/Zebra", @"/Library/MobileSubstrate", @"/usr/sbin/sshd",
            @"/usr/bin/ssh", @"/etc/apt", @"/var/lib/apt", @"/var/lib/dpkg",
            @"/var/lib/cydia", @"/bin/bash", @"/.installed_pal", @"/.bootstrapped",
            @"/var/binpack", @"/usr/lib/substitute", @"/usr/lib/TweakInject",
            @"/Library/TweakInject", @"substrate", @"SubstituteLoader", @"ellekit",
            @"ScaleTweak", @"Crane"];
    });
    for (NSString *f in frags) {
        if ([path containsString:f]) return YES;
    }
    return NO;
}

// Pour opendir: version C-string du test
static BOOL isJBCPath(const char *path) {
    if (!path) return NO;
    static const char *frags[] = {
        "/var/jb", "/Applications/Cydia", "/Applications/Sileo", "/Applications/Zebra",
        "/Library/MobileSubstrate", "/usr/sbin/sshd", "/usr/bin/ssh",
        "/etc/apt", "/var/lib/apt", "/var/lib/dpkg", "/var/lib/cydia",
        "/bin/bash", "/.installed_pal", "/.bootstrapped", "/var/binpack",
        "/usr/lib/substitute", "/usr/lib/TweakInject", "/Library/TweakInject",
        NULL
    };
    for (int i = 0; frags[i]; i++) {
        if (strstr(path, frags[i])) return YES;
    }
    // CRITIQUE: opendir("/bin") est le premier check de METADeviceAppearsJailbroken
    if (strcmp(path, "/bin") == 0) return YES;
    return NO;
}

static BOOL shouldHideDylib(const char *name) {
    if (!name) return NO;
    static const char *pats[] = {
        "ScaleTweak", "substrate", "Substrate", "SubstituteLoader", "TweakInject",
        "ellekit", "ElleKit", "Crane", "libhooker", "Choicy", "AppSync",
        "FridaGadget", "cycript", "MobileSubstrate", "pspawn", "rocketbootstrap", NULL
    };
    for (int i = 0; pats[i]; i++) {
        if (strstr(name, pats[i])) return YES;
    }
    return NO;
}

static void buildDylibMap(void) {
    uint32_t real = _dyld_image_count();
    if (_visibleMap) free(_visibleMap);
    _visibleMap = (uint32_t *)malloc(real * sizeof(uint32_t));
    _visibleCount = 0;
    for (uint32_t i = 0; i < real; i++) {
        if (!shouldHideDylib(_dyld_get_image_name(i)))
            _visibleMap[_visibleCount++] = i;
    }
}

// ═══════════════════════════════════════════════════════════════════════
// MARK: — JB BYPASS — Patch mémoire direct (AVANT que pthread_once ne run)
// ═══════════════════════════════════════════════════════════════════════
// METADeviceAppearsJailbroken cache à FBSharedFramework + 0x2CC3EC0
// METADeviceIsJailbroken cache à FBSharedFramework + 0x2CC3EC1
// On patch les bytes à 0 dès que FBSharedFramework est chargé

static void patchJBCacheBytes(const struct mach_header *header, intptr_t slide) {
    // Vérifier que c'est FBSharedFramework
    Dl_info info;
    if (!dladdr(header, &info) || !info.dli_fname) return;
    if (!strstr(info.dli_fname, "FBSharedFramework")) return;

    // Patcher les deux bytes de cache JB
    uint8_t *addrAppears = (uint8_t *)(slide + 0x2CC3EC0);
    uint8_t *addrIsJB    = (uint8_t *)(slide + 0x2CC3EC1);

    vm_address_t page = (vm_address_t)addrAppears & ~(vm_page_size - 1);
    kern_return_t kr = vm_protect(mach_task_self(), page, vm_page_size, false,
                                   VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY);
    if (kr == KERN_SUCCESS) {
        *addrAppears = 0;
        *addrIsJB = 0;
        // Également patcher le pthread_once token pour éviter la ré-exécution
        // Les tokens sont aux offsets 0x2AFC220 (Appears) et 0x2AFC230 (IsJB)
        // pthread_once_t = long; -1 = déjà exécuté
        int64_t *onceAppears = (int64_t *)(slide + 0x2AFC220);
        int64_t *onceIsJB    = (int64_t *)(slide + 0x2AFC230);
        vm_address_t oncePage = (vm_address_t)onceAppears & ~(vm_page_size - 1);
        kern_return_t kr2 = vm_protect(mach_task_self(), oncePage, vm_page_size, false,
                                        VM_PROT_READ | VM_PROT_WRITE | VM_PROT_COPY);
        if (kr2 == KERN_SUCCESS) {
            *onceAppears = -1;  // Marquer comme "déjà exécuté"
            *onceIsJB = -1;
        }
        scaleLog([NSString stringWithFormat:@"[JB-PATCH] OK — slide=0x%lx once=%d",
                  (unsigned long)slide, kr2 == KERN_SUCCESS]);
    } else {
        scaleLog([NSString stringWithFormat:@"[JB-PATCH] vm_protect failed: %d", kr]);
    }
}

// ═══════════════════════════════════════════════════════════════════════
// MARK: — Fishhook — C function rebinding (pas de trampoline, pas de rwx)
// ═══════════════════════════════════════════════════════════════════════

// --- opendir (CRITIQUE: premier check JB = opendir("/bin")) ---
static DIR *(*orig_opendir)(const char *);
static DIR *hook_opendir(const char *path) {
    if (_containerUUID && path && isJBCPath(path)) {
        errno = ENOENT;
        return NULL;
    }
    return orig_opendir(path);
}

// --- access ---
static int (*orig_access)(const char *, int);
static int hook_access(const char *path, int mode) {
    if (_containerUUID && path && isJBCPath(path)) return -1;
    return orig_access(path, mode);
}

// --- stat ---
static int (*orig_stat)(const char *, struct stat *);
static int hook_stat(const char *path, struct stat *buf) {
    if (_containerUUID && path && isJBCPath(path)) { errno = ENOENT; return -1; }
    return orig_stat(path, buf);
}

// --- lstat ---
static int (*orig_lstat)(const char *, struct stat *);
static int hook_lstat(const char *path, struct stat *buf) {
    if (_containerUUID && path && isJBCPath(path)) { errno = ENOENT; return -1; }
    return orig_lstat(path, buf);
}

// --- fopen ---
static FILE *(*orig_fopen)(const char *, const char *);
static FILE *hook_fopen(const char *path, const char *mode) {
    if (_containerUUID && path && isJBCPath(path)) { errno = ENOENT; return NULL; }
    return orig_fopen(path, mode);
}

// --- getifaddrs (masquer VPN/tunnel) ---
static int (*orig_getifaddrs)(struct ifaddrs **);
static int hook_getifaddrs(struct ifaddrs **ifap) {
    int result = orig_getifaddrs(ifap);
    if (result != 0 || !_containerUUID || !ifap || !*ifap) return result;
    struct ifaddrs *prev = NULL;
    struct ifaddrs *curr = *ifap;
    while (curr) {
        if (curr->ifa_name && (strncmp(curr->ifa_name, "utun", 4) == 0 ||
            strncmp(curr->ifa_name, "ipsec", 5) == 0 ||
            strncmp(curr->ifa_name, "ppp", 3) == 0)) {
            if (prev) prev->ifa_next = curr->ifa_next;
            else *ifap = curr->ifa_next;
            curr = curr->ifa_next;
        } else {
            prev = curr;
            curr = curr->ifa_next;
        }
    }
    return result;
}

// --- NSHomeDirectory ---
static NSString *(*orig_NSHomeDirectory)(void);
static NSString *hook_NSHomeDirectory(void) {
    if (_containerHome) return _containerHome;
    return orig_NSHomeDirectory();
}

// --- NSSearchPathForDirectoriesInDomains ---
static NSArray *(*orig_NSSearchPath)(NSSearchPathDirectory, NSSearchPathDomainMask, BOOL);
static NSArray *hook_NSSearchPath(NSSearchPathDirectory d, NSSearchPathDomainMask m, BOOL e) {
    NSArray *r = orig_NSSearchPath(d, m, e);
    if (!_containerHome || !_originalHome) return r;
    NSMutableArray *rr = [NSMutableArray new];
    for (NSString *p in r) {
        if ([p hasPrefix:_originalHome])
            [rr addObject:[_containerHome stringByAppendingString:[p substringFromIndex:_originalHome.length]]];
        else
            [rr addObject:p];
    }
    return rr;
}

// --- getenv ---
static char *(*orig_getenv)(const char *);
static char *hook_getenv(const char *n) {
    if (_containerHome && n && strcmp(n, "HOME") == 0) return (char *)[_containerHome UTF8String];
    if (n && strncmp(n, "DYLD_", 5) == 0) return NULL;
    return orig_getenv(n);
}

// IORegistryEntryCreateCFProperty — REMOVED (IG does not read IOKit directly)
// --- sysctlbyname ---
static int (*orig_sysctlbyname)(const char *, void *, size_t *, void *, size_t);
static int hook_sysctlbyname(const char *name, void *oldp, size_t *oldlenp, void *newp, size_t newlen) {
    if (!_containerUUID || !name) return orig_sysctlbyname(name, oldp, oldlenp, newp, newlen);
    if (strcmp(name, "kern.hostname") == 0 && oldp && oldlenp && _spoofHostname) {
        const char *h = [_spoofHostname UTF8String];
        size_t l = strlen(h) + 1;
        if (*oldlenp >= l) { memcpy(oldp, h, l); *oldlenp = l; return 0; }
    }
    if (strcmp(name, "kern.boottime") == 0 && oldp) {
        orig_sysctlbyname(name, oldp, oldlenp, newp, newlen);
        ((struct timeval *)oldp)->tv_sec -= _bootTimeOffset;
        return 0;
    }
    if (strcmp(name, "hw.memsize") == 0 && oldp && oldlenp && _containerUUID) {
        int r = orig_sysctlbyname(name, oldp, oldlenp, newp, newlen);
        if (r == 0 && *oldlenp >= sizeof(uint64_t)) {
            unsigned char h[32];
            hashSeed([[NSString stringWithFormat:@"%@_memsize", _containerUUID] UTF8String], h);
            int64_t offset = ((int64_t)(h[0] % 5) - 2) * 256 * 1024 * 1024;
            uint64_t *mem = (uint64_t *)oldp;
            *mem = (uint64_t)((int64_t)*mem + offset);
        }
        return r;
    }
    if ((strcmp(name, "hw.physicalcpu_max") == 0 || strcmp(name, "hw.logicalcpu") == 0
         || strcmp(name, "hw.ncpu") == 0 || strcmp(name, "hw.logicalcpu_max") == 0)
        && oldp && oldlenp && _containerUUID) {
        int r = orig_sysctlbyname(name, oldp, oldlenp, newp, newlen);
        if (r == 0 && *oldlenp >= sizeof(int)) {
            unsigned char h[32];
            hashSeed([[NSString stringWithFormat:@"%@_cpu", _containerUUID] UTF8String], h);
            int cores = 4 + (h[0] % 3);
            *(int *)oldp = cores;
        }
        return r;
    }
    return orig_sysctlbyname(name, oldp, oldlenp, newp, newlen);
}

// --- CNCopyCurrentNetworkInfo (BSSID spoofing) ---
static CFDictionaryRef (*orig_CNCopy)(CFStringRef);
static CFDictionaryRef hook_CNCopy(CFStringRef interfaceName) {
    CFDictionaryRef orig = orig_CNCopy(interfaceName);
    if (!_containerUUID || !orig) return orig;
    NSMutableDictionary *m = [(__bridge NSDictionary *)orig mutableCopy];
    CFRelease(orig);
    if (_spoofBSSID) m[@"BSSID"] = _spoofBSSID;
    if (_spoofSSID) {
        m[@"SSID"] = _spoofSSID;
        m[@"SSIDDATA"] = [_spoofSSID dataUsingEncoding:NSUTF8StringEncoding];
    }
    return (__bridge_retained CFDictionaryRef)m;
}

// --- _dyld_image_count / _dyld_get_image_name ---
static uint32_t (*orig_dyld_image_count)(void);
static uint32_t hook_dyld_image_count(void) {
    if (!_containerUUID) return orig_dyld_image_count();
    return _visibleCount;
}

// _dyld_get_image_name — via %hookf (fishhook can't rebind this on chained fixups)
%hookf(const char *, _dyld_get_image_name, uint32_t idx) {
    if (!_containerUUID) return %orig;
    if (idx < _visibleCount) return %orig(_visibleMap[idx]);
    return %orig;
}

// --- dlopen (bloquer les libs JB) ---
static void *(*orig_dlopen)(const char *, int);
static void *hook_dlopen(const char *path, int mode) {
    if (_containerUUID && path && shouldHideDylib(path)) return NULL;
    return orig_dlopen(path, mode);
}

// --- SecItem* (keychain scoping) ---
static BOOL isSharedKC(NSDictionary *q) {
    NSString *grp = q[(__bridge id)kSecAttrAccessGroup];
    if (grp && ([grp isEqualToString:@"group.com.facebook.family"] ||
                [grp isEqualToString:@"group.com.burbn.family"] ||
                [grp isEqualToString:@"MH9GU9K5PX.platformFamily"] ||
                [grp isEqualToString:@"MH9GU9K5PX.shared"]))
        return YES;
    NSString *svc = q[(__bridge id)kSecAttrService];
    if (svc && ([svc containsString:@"MachineID"] || [svc containsString:@"familydeviceid"]))
        return YES;
    return NO;
}

static NSMutableDictionary *kcScope(NSDictionary *q) {
    if (!_containerUUID || !q) return [q mutableCopy];
    NSMutableDictionary *s = [q mutableCopy];
    NSString *sv = s[(__bridge id)kSecAttrService];
    if (sv) s[(__bridge id)kSecAttrService] = [NSString stringWithFormat:@"_sc_%@_%@", _containerUUID, sv];
    NSString *a = s[(__bridge id)kSecAttrAccount];
    if (a) s[(__bridge id)kSecAttrAccount] = [NSString stringWithFormat:@"_sc_%@_%@", _containerUUID, a];
    if (!a && isSharedKC(q))
        s[(__bridge id)kSecAttrAccount] = [NSString stringWithFormat:@"_sc_%@", _containerUUID];
    if (!sv && !a) {
        NSString *l = s[(__bridge id)kSecAttrLabel] ?: @"";
        s[(__bridge id)kSecAttrLabel] = [NSString stringWithFormat:@"_sc_%@_%@", _containerUUID, l];
    }
    return s;
}

static OSStatus (*orig_SecItemAdd)(CFDictionaryRef, CFTypeRef *);
static OSStatus hook_SecItemAdd(CFDictionaryRef a, CFTypeRef *r) {
    if (!_containerUUID) return orig_SecItemAdd(a, r);
    return orig_SecItemAdd((__bridge CFDictionaryRef)kcScope((__bridge NSDictionary *)a), r);
}

static OSStatus (*orig_SecItemCopyMatching)(CFDictionaryRef, CFTypeRef *);
static OSStatus hook_SecItemCopyMatching(CFDictionaryRef q, CFTypeRef *r) {
    if (_containerUUID) {
        NSString *grp = (__bridge NSString *)CFDictionaryGetValue(q, kSecAttrAccessGroup);
        NSString *svc = (__bridge NSString *)CFDictionaryGetValue(q, kSecAttrService);
        NSString *acct = (__bridge NSString *)CFDictionaryGetValue(q, kSecAttrAccount);
        if (grp && ([grp containsString:@"platformFamily"] || [grp containsString:@".shared"])) {
            static int sso_log = 0;
            if (sso_log < 10) {
                sso_log++;
                scaleLog([NSString stringWithFormat:@"[KC-SSO-READ] grp=%@ svc=%@ acct=%@", grp, svc?:@"-", acct?:@"-"]);
            }
        }
    }
    if (!_containerUUID) return orig_SecItemCopyMatching(q, r);
    return orig_SecItemCopyMatching((__bridge CFDictionaryRef)kcScope((__bridge NSDictionary *)q), r);
}

static OSStatus (*orig_SecItemUpdate)(CFDictionaryRef, CFDictionaryRef);
static OSStatus hook_SecItemUpdate(CFDictionaryRef q, CFDictionaryRef a) {
    if (!_containerUUID) return orig_SecItemUpdate(q, a);
    return orig_SecItemUpdate((__bridge CFDictionaryRef)kcScope((__bridge NSDictionary *)q), a);
}

static OSStatus (*orig_SecItemDelete)(CFDictionaryRef);
static OSStatus hook_SecItemDelete(CFDictionaryRef q) {
    if (!_containerUUID) return orig_SecItemDelete(q);
    return orig_SecItemDelete((__bridge CFDictionaryRef)kcScope((__bridge NSDictionary *)q));
}


// ═══════════════════════════════════════════════════════════════════════
// MARK: — ObjC hooks (method_exchangeImplementations via Logos — natif, safe)
// ═══════════════════════════════════════════════════════════════════════

%hook NSFileManager

- (BOOL)fileExistsAtPath:(NSString *)path {
    if (isJBPath(path)) return NO;
    return %orig;
}

- (BOOL)fileExistsAtPath:(NSString *)path isDirectory:(BOOL *)d {
    if (isJBPath(path)) return NO;
    return %orig;
}

- (BOOL)isReadableFileAtPath:(NSString *)path {
    if (isJBPath(path)) return NO;
    return %orig;
}

- (NSURL *)containerURLForSecurityApplicationGroupIdentifier:(NSString *)gid {
    if (_containerUUID && gid &&
        ([gid containsString:@"facebook"] || [gid containsString:@"instagram"] || [gid containsString:@"burbn"])) {
        NSString *gdir = [[_containerHome stringByAppendingPathComponent:@"Library/GroupContainers"]
                          stringByAppendingPathComponent:gid];
        [[NSFileManager defaultManager] createDirectoryAtPath:gdir
                                  withIntermediateDirectories:YES attributes:nil error:nil];
        return [NSURL fileURLWithPath:gdir];
    }
    return %orig;
}

- (NSArray *)URLsForDirectory:(NSSearchPathDirectory)d inDomains:(NSSearchPathDomainMask)m {
    NSArray *r = %orig;
    if (!_containerHome || !_originalHome) return r;
    NSMutableArray *rr = [NSMutableArray new];
    for (NSURL *u in r) {
        NSString *p = [u path];
        if ([p hasPrefix:_originalHome])
            [rr addObject:[NSURL fileURLWithPath:[_containerHome stringByAppendingString:[p substringFromIndex:_originalHome.length]]]];
        else
            [rr addObject:u];
    }
    return rr;
}


- (NSDictionary *)attributesOfFileSystemForPath:(NSString *)path error:(NSError **)error {
    NSDictionary *orig = %orig;
    if (!_containerUUID || !orig) return orig;
    NSMutableDictionary *m = [orig mutableCopy];
    NSNumber *freeSize = m[NSFileSystemFreeSize];
    if (freeSize && _diskSpaceOffset != 0) {
        long long adjusted = [freeSize longLongValue] + _diskSpaceOffset;
        if (adjusted > 1024*1024*1024) { m[NSFileSystemFreeSize] = @(adjusted); }
    }
    return [m copy];
}

%end

// --- JB bypass: bloquer l'écriture test /tmp/jb_test_ ---
%hook NSString

- (BOOL)writeToFile:(NSString *)path atomically:(BOOL)atomic encoding:(NSStringEncoding)enc error:(NSError **)err {
    if (_containerUUID && path && [path hasPrefix:@"/tmp/jb_test_"]) {
        if (err) *err = [NSError errorWithDomain:NSCocoaErrorDomain code:NSFileWriteNoPermissionError userInfo:nil];
        return NO;
    }
    return %orig;
}

%end

%hook UIApplication

- (BOOL)canOpenURL:(NSURL *)url {
    NSString *s = [[url scheme] lowercaseString];
    if ([s isEqualToString:@"cydia"] || [s isEqualToString:@"sileo"] ||
        [s isEqualToString:@"zebra"] || [s isEqualToString:@"filza"]) return NO;
    return %orig;
}

%end

%hook NEHotspotNetwork

- (NSString *)BSSID {
    if (_containerUUID && _spoofBSSID) return _spoofBSSID;
    return %orig;
}

- (NSString *)SSID {
    if (_containerUUID && _spoofSSID) return _spoofSSID;
    return %orig;
}

%end


// ═══ Session persistence — per-container cache for critical keys ═══
static NSMutableDictionary *_prefsCache = nil;
static NSString *_prefsCachePath = nil;

static NSArray *_criticalKeys(void) {
    static NSArray *keys;
    static dispatch_once_t once;
    dispatch_once(&once, ^{
        keys = @[@"previouslyLoggedInUserId", @"logged-out-data",
                 @"FBAnalyticsCurrentLoggedInUserIdentityDict",
                 @"mobileconfig_first_user_session_id",
                 @"last-logged-in-account-dict", @"user-has-logged-in-once",
                 @"kFBPreviousAppSessionID", @"ndx_trigger_is_session_change",
                 @"profile-title-tooltip-new-logged-in-ig-account-count-key",
                 @"switcher-education-logged-in-account-count-key"];
    });
    return keys;
}

static void _savePrefsCache(void) {
    if (_prefsCache && _prefsCachePath)
        [_prefsCache writeToFile:_prefsCachePath atomically:YES];
}

%hook NSUserDefaults

- (instancetype)initWithSuiteName:(NSString *)s {
    if (_containerUUID && s && [s containsString:@"group.com.burbn"]) {
        static int _suite_log = 0;
        if (_suite_log < 5) {
            _suite_log++;
            scaleLog([NSString stringWithFormat:@"[SUITE] %@ -> scale_%@_%@", s, [_containerUUID substringToIndex:8], s]);
        }
    }
    if (_containerUUID && s && ![s hasPrefix:@"_sc_"] && ![s hasPrefix:@"scale_"]) {
        if ([s hasPrefix:@"group."])
            return %orig([NSString stringWithFormat:@"scale_%@_%@", _containerUUID, s]);
        return %orig([NSString stringWithFormat:@"_sc_%@_%@", _containerUUID, s]);
    }
    return %orig;
}

- (id)objectForKey:(NSString *)key {
    if (_containerUUID && key && ([key containsString:@"last_logged_in_user"] || [key containsString:@"persistent_accounts"] || [key containsString:@"sessiondata"])) {
        static int _obj_log = 0;
        if (_obj_log < 10) {
            _obj_log++;
            id val = %orig;
            scaleLog([NSString stringWithFormat:@"[UD-READ] %@ = %@", key, val ? @"PRESENT" : @"nil"]);
        }
    }
    if (_containerUUID && _prefsCache && key && [_criticalKeys() containsObject:key]) {
        if ([key isEqualToString:@"logged-out-data"]) return nil;
        id val = _prefsCache[key];
        if (val) return [val isEqual:[NSNull null]] ? nil : val;
        id origVal = %orig;
        _prefsCache[key] = origVal ?: [NSNull null];
        _savePrefsCache();
        return origVal;
    }
    return %orig;
}

- (void)setObject:(id)value forKey:(NSString *)key {
    %orig;
    if (_containerUUID && _prefsCache && key && [_criticalKeys() containsObject:key]) {
        if ([key isEqualToString:@"logged-out-data"]) return;
        _prefsCache[key] = value ?: [NSNull null];
        _savePrefsCache();
        scaleLog([NSString stringWithFormat:@"[UD-SAVE] %@", key]);
    }
}

- (void)removeObjectForKey:(NSString *)key {
    %orig;
    if (_containerUUID && _prefsCache && key && [_criticalKeys() containsObject:key]) {
        _prefsCache[key] = [NSNull null];
        _savePrefsCache();
    }
}

%end

%hook UIDevice

- (NSUUID *)identifierForVendor {
    if (_spoofIDFV) return [[NSUUID alloc] initWithUUIDString:_spoofIDFV];
    return %orig;
}

- (NSString *)name {
    if (_spoofDeviceName) return _spoofDeviceName;
    return %orig;
}

- (float)batteryLevel {
    if (_containerUUID) return _spoofBattery;
    return %orig;
}

%end

%hook ASIdentifierManager

- (NSUUID *)advertisingIdentifier {
    if (_spoofIDFA) return [[NSUUID alloc] initWithUUIDString:_spoofIDFA];
    return %orig;
}

%end

%hook NSProcessInfo

- (NSTimeInterval)systemUptime {
    if (_containerUUID) return %orig + _bootTimeOffset;
    return %orig;
}

%end

%hook NSTimeZone

+ (NSTimeZone *)localTimeZone {
    if (_spoofTimezone) return [NSTimeZone timeZoneWithName:_spoofTimezone];
    return %orig;
}

+ (NSTimeZone *)systemTimeZone {
    if (_spoofTimezone) return [NSTimeZone timeZoneWithName:_spoofTimezone];
    return %orig;
}

%end

%hook NSLocale

+ (NSLocale *)currentLocale {
    if (_spoofLocale) return [[NSLocale alloc] initWithLocaleIdentifier:_spoofLocale];
    return %orig;
}

+ (NSArray *)preferredLanguages {
    if (_spoofLocale) {
        NSString *lang = [[_spoofLocale componentsSeparatedByString:@"_"] firstObject];
        return @[_spoofLocale, lang];
    }
    return %orig;
}

%end

%hook NSMutableURLRequest

- (void)setValue:(NSString *)val forHTTPHeaderField:(NSString *)field {


    if (_spoofUserAgent && field && [field isEqualToString:@"User-Agent"] && val && [val containsString:@"Instagram"]) {
        val = _spoofUserAgent;
    }

    if (field && [field hasPrefix:@"TFB-TCP-Fingerprint"] && val) {
        unsigned char h[32];
        hashSeed([[NSString stringWithFormat:@"%@_tfb_%@", _containerUUID, field] UTF8String], h);
        NSString *suffix = [NSString stringWithFormat:@"%02x%02x", h[0], h[1]];
        if (val.length > 4) {
            val = [[val substringToIndex:val.length - 4] stringByAppendingString:suffix];
        }
    }
    if (field && [field isEqualToString:@"TFB-HTTP-Fingerprint"] && val) {
        unsigned char h[32];
        hashSeed([[NSString stringWithFormat:@"%@_tfb_http", _containerUUID] UTF8String], h);
        NSString *suffix = [NSString stringWithFormat:@"%02x%02x", h[0], h[1]];
        if (val.length > 4) {
            val = [[val substringToIndex:val.length - 4] stringByAppendingString:suffix];
        }
    }

    if (field && [field isEqualToString:@"TFB-Orig-Client-IP"]) {
        return;
    }
    if (field && [field isEqualToString:@"TFB-Orig-Client-Port"]) {
        return;
    }

    %orig(val, field);
}

%end


// ═══════════════════════════════════════════════════════════════════════
// MARK: — EARLY INIT
// ═══════════════════════════════════════════════════════════════════════


// FB*Directory hooks — redirect Meta path functions to container

static NSString *(*orig_FBAppSupportDir)(void);
static NSString *hook_FBAppSupportDir(void) {
    scaleLog([NSString stringWithFormat:@"[FB-CALL] AppSupport -> %@", _containerHome ?: @"nil"]);
    if (_containerHome) {
        NSString *p = [_containerHome stringByAppendingPathComponent:@"Library/Application Support"];
        [[NSFileManager defaultManager] createDirectoryAtPath:p withIntermediateDirectories:YES attributes:nil error:nil];
        return p;
    }
    return orig_FBAppSupportDir();
}

static NSString *(*orig_FBAppSupportDirSub)(NSString *);
static NSString *hook_FBAppSupportDirSub(NSString *sub) {
    if (_containerHome) {
        NSString *base = [_containerHome stringByAppendingPathComponent:@"Library/Application Support"];
        NSString *p = sub ? [base stringByAppendingPathComponent:sub] : base;
        [[NSFileManager defaultManager] createDirectoryAtPath:p withIntermediateDirectories:YES attributes:nil error:nil];
        return p;
    }
    return orig_FBAppSupportDirSub(sub);
}

static NSString *(*orig_FBLibDir)(void);
static NSString *hook_FBLibDir(void) {
    scaleLog([NSString stringWithFormat:@"[FB-CALL] Library -> %@", _containerHome ?: @"nil"]);
    if (_containerHome) {
        NSString *p = [_containerHome stringByAppendingPathComponent:@"Library"];
        [[NSFileManager defaultManager] createDirectoryAtPath:p withIntermediateDirectories:YES attributes:nil error:nil];
        return p;
    }
    return orig_FBLibDir();
}

static NSString *(*orig_FBDocsDir)(void);
static NSString *hook_FBDocsDir(void) {
    if (_containerHome) {
        NSString *p = [_containerHome stringByAppendingPathComponent:@"Documents"];
        [[NSFileManager defaultManager] createDirectoryAtPath:p withIntermediateDirectories:YES attributes:nil error:nil];
        return p;
    }
    return orig_FBDocsDir();
}

static NSString *(*orig_FBCachesDir)(void);
static NSString *hook_FBCachesDir(void) {
    if (_containerHome) {
        NSString *p = [_containerHome stringByAppendingPathComponent:@"Library/Caches"];
        [[NSFileManager defaultManager] createDirectoryAtPath:p withIntermediateDirectories:YES attributes:nil error:nil];
        return p;
    }
    return orig_FBCachesDir();
}

static NSURL *(*orig_FBCachesURL)(void);
static NSURL *hook_FBCachesURL(void) {
    if (_containerHome) {
        NSString *p = [_containerHome stringByAppendingPathComponent:@"Library/Caches"];
        [[NSFileManager defaultManager] createDirectoryAtPath:p withIntermediateDirectories:YES attributes:nil error:nil];
        return [NSURL fileURLWithPath:p];
    }
    return orig_FBCachesURL();
}


static void installFishhooks(void) {
    struct rebinding fb_rebindings[] = {
        {"FBApplicationSupportDirectory",            (void *)hook_FBAppSupportDir,    (void **)&orig_FBAppSupportDir},
        {"FBApplicationSupportDirectoryWithSubPath", (void *)hook_FBAppSupportDirSub, (void **)&orig_FBAppSupportDirSub},
        {"FBLibraryDirectory",                       (void *)hook_FBLibDir,           (void **)&orig_FBLibDir},
        {"FBDocumentsDirectory",                     (void *)hook_FBDocsDir,          (void **)&orig_FBDocsDir},
        {"FBCachesDirectory",                        (void *)hook_FBCachesDir,        (void **)&orig_FBCachesDir},
        {"FBCachesURL",                              (void *)hook_FBCachesURL,        (void **)&orig_FBCachesURL},
    };
    int fb_result = rebind_symbols(fb_rebindings, 6);
    scaleLog([NSString stringWithFormat:@"[FB-DIRS] rebind result=%d", fb_result]);


    struct rebinding rebindings[] = {
        // JB bypass
        {"opendir",       (void *)hook_opendir,       (void **)&orig_opendir},
        {"access",        (void *)hook_access,         (void **)&orig_access},
        {"stat",          (void *)hook_stat,           (void **)&orig_stat},
        {"lstat",         (void *)hook_lstat,          (void **)&orig_lstat},
        {"fopen",         (void *)hook_fopen,          (void **)&orig_fopen},
        {"dlopen",        (void *)hook_dlopen,         (void **)&orig_dlopen},
        {"getenv",        (void *)hook_getenv,         (void **)&orig_getenv},
        // Network
        {"getifaddrs",    (void *)hook_getifaddrs,     (void **)&orig_getifaddrs},
        {"CNCopyCurrentNetworkInfo", (void *)hook_CNCopy, (void **)&orig_CNCopy},
        // Identity
        // IORegistryEntryCreateCFProperty removed — IG does not use IOKit
        {"sysctlbyname",  (void *)hook_sysctlbyname,  (void **)&orig_sysctlbyname},
        // Keychain
        {"SecItemAdd",          (void *)hook_SecItemAdd,          (void **)&orig_SecItemAdd},
        {"SecItemCopyMatching", (void *)hook_SecItemCopyMatching, (void **)&orig_SecItemCopyMatching},
        {"SecItemUpdate",       (void *)hook_SecItemUpdate,       (void **)&orig_SecItemUpdate},
        {"SecItemDelete",       (void *)hook_SecItemDelete,       (void **)&orig_SecItemDelete},
        // Filesystem
        {"NSHomeDirectory", (void *)hook_NSHomeDirectory, (void **)&orig_NSHomeDirectory},
        {"NSSearchPathForDirectoriesInDomains", (void *)hook_NSSearchPath, (void **)&orig_NSSearchPath},
        // Dylib hiding
        {"_dyld_image_count",    (void *)hook_dyld_image_count,    (void **)&orig_dyld_image_count},
    };
    rebind_symbols(rebindings, sizeof(rebindings) / sizeof(rebindings[0]));
}


// ═══ COOKIES — inject saved session at runtime ═══
static void injectSavedCookies(void) {
    NSString *cookiePath = [_containerHome stringByAppendingPathComponent:@"Library/Cookies/scale_cookies.dat"];
    NSData *data = [NSData dataWithContentsOfFile:cookiePath];
    if (!data) return;
    NSArray *cookies = nil;
    @try {
        cookies = [NSKeyedUnarchiver unarchiveObjectWithData:data];
    } @catch (NSException *e) { return; }
    if (![cookies isKindOfClass:[NSArray class]] || cookies.count == 0) return;
    NSHTTPCookieStorage *jar = [NSHTTPCookieStorage sharedHTTPCookieStorage];
    int injected = 0;
    for (NSHTTPCookie *cookie in cookies) {
        if ([cookie isKindOfClass:[NSHTTPCookie class]]) { [jar setCookie:cookie]; injected++; }
    }
    if (injected > 0) scaleLog([NSString stringWithFormat:@"[COOKIES] Injected %d", injected]);
}

// ═══ BATTERY — realistic decay ═══
static float loadBatteryState(void) {
    if (!_batteryStatePath) return -1;
    NSDictionary *state = [NSDictionary dictionaryWithContentsOfFile:_batteryStatePath];
    if (!state) return -1;
    float level = [state[@"level"] floatValue];
    NSTimeInterval lastSeen = [state[@"timestamp"] doubleValue];
    NSTimeInterval now = [[NSDate date] timeIntervalSince1970];
    double hours = (now - lastSeen) / 3600.0;
    
    // Deterministic randomness for this session
    unsigned char h[CC_SHA256_DIGEST_LENGTH];
    hashSeed([[NSString stringWithFormat:@"%@_ses_%ld", _containerUUID, (long)now/300] UTF8String], h);
    float rand01 = h[0] / 255.0;
    
    if (hours > 8.0) {
        // Overnight / long break — phone was charged
        // Random 65-100%, biased toward high
        return 0.65 + rand01 * 0.35;
    } else if (hours > 2.0) {
        // Few hours away — standby drain ~0.5%/h + maybe partial charge
        float drain = hours * (0.003 + rand01 * 0.004); // 0.3-0.7% per hour
        float maybeCharge = (h[1] > 180) ? (0.10 + (h[2]/255.0) * 0.30) : 0; // 30% chance of partial charge
        float newLevel = level - drain + maybeCharge;
        if (newLevel > 1.0) newLevel = 0.90 + rand01 * 0.08;
        if (newLevel < 0.15) newLevel = 0.15 + rand01 * 0.10;
        return newLevel;
    } else if (hours > 0.5) {
        // Short break — standby drain ~2%/h
        float drain = hours * (0.015 + rand01 * 0.010); // 1.5-2.5% per hour
        float newLevel = level - drain;
        if (newLevel < 0.15) newLevel = 0.15;
        return newLevel;
    } else {
        // Just closed and reopened — light drain ~3%/h
        float drain = hours * (0.02 + rand01 * 0.015); // 2-3.5% per hour
        float newLevel = level - drain;
        if (newLevel < 0.15) newLevel = 0.15;
        return newLevel;
    }
}

static void saveBatteryState(float level) {
    if (!_batteryStatePath) return;
    [@{@"level": @(level), @"timestamp": @([[NSDate date] timeIntervalSince1970])} writeToFile:_batteryStatePath atomically:YES];
}

static float currentBattery(void) {
    NSTimeInterval elapsed = [[NSDate date] timeIntervalSince1970] - _batterySessionStart;
    unsigned char h[CC_SHA256_DIGEST_LENGTH];
    hashSeed([[NSString stringWithFormat:@"%@_drain", _containerUUID] UTF8String], h);
    float drainPerSec = (0.001 + (h[0] / 255.0) * 0.002) / 60.0;
    float level = _batteryStartLevel - (elapsed * drainPerSec);
    return level < 0.15 ? 0.15 : level;
}

static void startBatteryTimer(void) {
    dispatch_source_t timer = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, dispatch_get_main_queue());
    dispatch_source_set_timer(timer, dispatch_time(DISPATCH_TIME_NOW, 60*NSEC_PER_SEC), 60*NSEC_PER_SEC, 5*NSEC_PER_SEC);
    dispatch_source_set_event_handler(timer, ^{
        _spoofBattery = currentBattery();
        saveBatteryState(_spoofBattery);
    });
    dispatch_resume(timer);
}


// ═══ PHASE 4 — Challenge Detection ═══

static void writeAlert(NSString *type, NSString *detail, int statusCode) {
    NSString *line = [NSString stringWithFormat:@"%@ [%@] container=%@ status=%d %@\n",
        [NSDate date], type, _containerUUID ?: @"default", statusCode, detail ?: @""];
    NSFileHandle *fh = [NSFileHandle fileHandleForWritingAtPath:@"/tmp/scale_alerts.log"];
    if (!fh) {
        [line writeToFile:@"/tmp/scale_alerts.log" atomically:YES encoding:NSUTF8StringEncoding error:nil];
    } else {
        [fh seekToEndOfFile];
        [fh writeData:[line dataUsingEncoding:NSUTF8StringEncoding]];
        [fh closeFile];
    }
}

static void checkResponse(NSData *data, NSHTTPURLResponse *resp, NSURL *url) {
    if (!data || data.length == 0 || !_containerUUID) return;
    int code = resp ? (int)resp.statusCode : 0;
    if (code == 400 || code == 403 || code == 429) {
        NSString *body = [[NSString alloc] initWithData:[data subdataWithRange:NSMakeRange(0, MIN(data.length, 500))] encoding:NSUTF8StringEncoding];
        if (!body) return;
        if ([body containsString:@"challenge_required"] || [body containsString:@"checkpoint_required"])
            { writeAlert(@"CHALLENGE", [url absoluteString], code); return; }
        if ([body containsString:@"login_required"])
            { writeAlert(@"LOGIN_REQUIRED", [url absoluteString], code); return; }
        if ([body containsString:@"feedback_required"])
            { writeAlert(@"FEEDBACK", [url absoluteString], code); return; }
        if ([body containsString:@"consent_required"])
            { writeAlert(@"CONSENT", [url absoluteString], code); return; }
        if ([body containsString:@"suspicious_activity"])
            { writeAlert(@"SUSPICIOUS", [url absoluteString], code); return; }
        if ([body containsString:@"spam"])
            { writeAlert(@"SPAM", [url absoluteString], code); return; }
    }
    if (code == 429) writeAlert(@"RATE_LIMIT", [url absoluteString], code);
}

%hook NSURLSession
- (NSURLSessionDataTask *)dataTaskWithRequest:(NSURLRequest *)request completionHandler:(void (^)(NSData *, NSURLResponse *, NSError *))handler {
    if (!_containerUUID || !handler) return %orig;
    NSString *host = request.URL.host;
    if (!host || (![host containsString:@"instagram"] && ![host containsString:@"facebook"] && ![host containsString:@"threads"] && ![host containsString:@"threads"]))
        return %orig;
    void (^wrapped)(NSData *, NSURLResponse *, NSError *) = ^(NSData *data, NSURLResponse *response, NSError *error) {
        if (data && [response isKindOfClass:[NSHTTPURLResponse class]])
            checkResponse(data, (NSHTTPURLResponse *)response, request.URL);
        handler(data, response, error);
    };
    return %orig(request, [wrapped copy]);
}
%end


// ═══ SESSION CAPTURE — dump cookies for API use ═══

static void dumpSessionToFile(void) {
    if (!_containerHome || !_containerUUID) return;
    NSHTTPCookieStorage *jar = [NSHTTPCookieStorage sharedHTTPCookieStorage];
    NSArray *cookies = [jar cookiesForURL:[NSURL URLWithString:@"https://www.instagram.com/"]];
    if (cookies.count == 0) return;
    NSMutableDictionary *session = [NSMutableDictionary new];
    for (NSHTTPCookie *c in cookies) { session[c.name] = c.value; }
    if (!session[@"sessionid"]) return;
    NSString *path = [_containerHome stringByAppendingPathComponent:@"Library/session.json"];
    NSData *json = [NSJSONSerialization dataWithJSONObject:session options:NSJSONWritingPrettyPrinted error:nil];
    [json writeToFile:path atomically:YES];
}

%hook NSHTTPCookieStorage
- (void)setCookie:(NSHTTPCookie *)cookie {
    %orig;
    if (_containerUUID && cookie && [[cookie domain] containsString:@"instagram"]) {
        static NSTimeInterval lastDump = 0;
        NSTimeInterval now = [[NSDate date] timeIntervalSince1970];
        if (now - lastDump > 30) {
            lastDump = now;
            dispatch_async(dispatch_get_global_queue(0, 0), ^{ dumpSessionToFile(); });
        }
    }
}
%end





// ═══ Spotlight — block indexing for containers ═══

// --- WKWebView cookie isolation ---
%hook WKWebsiteDataStore
+ (WKWebsiteDataStore *)defaultDataStore {
    if (_containerUUID) {
        return [WKWebsiteDataStore nonPersistentDataStore];
    }
    return %orig;
}
%end

// --- Font list filtering ---
%hook UIFont
+ (NSArray<NSString *> *)familyNames {
    NSArray *orig = %orig;
    if (!_containerUUID) return orig;
    static NSSet *stockFonts = nil;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        stockFonts = [NSSet setWithArray:@[
            @"Academy Engraved LET", @"Al Nile", @"American Typewriter",
            @"Apple Color Emoji", @"Apple SD Gothic Neo", @"Apple Symbols",
            @"Arial", @"Arial Hebrew", @"Arial Rounded MT Bold", @"Avenir",
            @"Avenir Next", @"Avenir Next Condensed", @"Baskerville",
            @"Bodoni 72", @"Bodoni 72 Oldstyle", @"Bodoni 72 Smallcaps",
            @"Bodoni Ornaments", @"Bradley Hand", @"Chalkboard SE",
            @"Chalkduster", @"Cochin", @"Copperplate", @"Courier",
            @"Courier New", @"Damascus", @"Devanagari Sangam MN",
            @"Didot", @"DIN Alternate", @"DIN Condensed",
            @"Euphemia UCAS", @"Farah", @"Futura", @"Galvji",
            @"Geeza Pro", @"Georgia", @"Gill Sans", @"Grantha Sangam MN",
            @"Helvetica", @"Helvetica Neue", @"Hiragino Maru Gothic ProN",
            @"Hiragino Mincho ProN", @"Hiragino Sans", @"Hoefler Text",
            @"Impact", @"Iowan Old Style", @"Kailasa", @"Kefa",
            @"Khmer Sangam MN", @"Kohinoor Bangla", @"Kohinoor Devanagari",
            @"Kohinoor Gujarati", @"Kohinoor Telugu", @"Lao Sangam MN",
            @"Malayalam Sangam MN", @"Marker Felt", @"Menlo",
            @"Mishafi", @"Mukta Mahee", @"Myanmar Sangam MN",
            @"Noteworthy", @"Noto Nastaliq Urdu", @"Noto Sans Kannada",
            @"Noto Sans Myanmar", @"Noto Sans Oriya", @"Optima",
            @"Palatino", @"Papyrus", @"Party LET", @"PingFang HK",
            @"PingFang SC", @"PingFang TC", @"Rockwell", @"Savoye LET",
            @"SF Compact", @"SF Mono", @"SF Pro", @"SF Pro Display",
            @"SF Pro Rounded", @"SF Pro Text", @"Sinhala Sangam MN",
            @"Snell Roundhand", @"Symbol", @"Tamil Sangam MN",
            @"Thonburi", @"Times New Roman", @"Trebuchet MS",
            @"Verdana", @"Zapf Dingbats", @"Zapfino",
        ]];
    });
    NSMutableArray *filtered = [NSMutableArray array];
    for (NSString *f in orig) {
        if ([stockFonts containsObject:f]) [filtered addObject:f];
    }
    return [filtered copy];
}
%end

// --- Bluetooth state ---
%hook CBCentralManager
- (NSInteger)state {
    if (_containerUUID) return 4;
    return %orig;
}
%end

%hook CSSearchableIndex
- (void)indexSearchableItems:(NSArray *)items completionHandler:(void (^)(NSError *))handler {
    if (_containerUUID) {
        if (handler) handler(nil);
        return;
    }
    %orig;
}
%end

// ═══ Pasteboard — return empty for containers ═══
%hook UIPasteboard
+ (id)generalPasteboard {
    if (_containerUUID) {
        return nil;
    }
    return %orig;
}
%end

// ═══ CloudKit — disable for containers ═══
%hook CKContainer
+ (CKContainer *)defaultContainer {
    if (_containerUUID) return nil;
    return %orig;
}
%end

// ═══ Push notifications — block deviceToken registration per container ═══
%hook UIApplication
- (void)registerForRemoteNotifications {
    if (_containerUUID) {
        scaleLog(@"[PUSH] Blocked registerForRemoteNotifications");
        return;
    }
    %orig;
}
%end

// ═══ Proxy — apply per-container proxy from config ═══

static void parseProxyString(NSString *proxy) {
    if (!proxy || proxy.length == 0) return;
    // Formats: host:port  or  user:pass@host:port
    NSString *hostPort = proxy;
    NSRange atRange = [proxy rangeOfString:@"@"];
    if (atRange.location != NSNotFound) {
        NSString *userPass = [proxy substringToIndex:atRange.location];
        hostPort = [proxy substringFromIndex:atRange.location + 1];
        NSRange colonRange = [userPass rangeOfString:@":"];
        if (colonRange.location != NSNotFound) {
            _proxyUser = [userPass substringToIndex:colonRange.location];
            _proxyPass = [userPass substringFromIndex:colonRange.location + 1];
        }
    }
    NSRange colonRange = [hostPort rangeOfString:@":" options:NSBackwardsSearch];
    if (colonRange.location != NSNotFound) {
        _proxyHost = [hostPort substringToIndex:colonRange.location];
        _proxyPort = [[hostPort substringFromIndex:colonRange.location + 1] intValue];
    }
}

%hook NSURLSessionConfiguration

- (NSDictionary *)connectionProxyDictionary {
    if (_containerUUID && _proxyHost && _proxyPort > 0) {
        NSMutableDictionary *proxy = [NSMutableDictionary new];
        proxy[@"HTTPEnable"] = @YES;
        proxy[@"HTTPProxy"] = _proxyHost;
        proxy[@"HTTPPort"] = @(_proxyPort);
        proxy[@"HTTPSEnable"] = @YES;
        proxy[@"HTTPSProxy"] = _proxyHost;
        proxy[@"HTTPSPort"] = @(_proxyPort);
        if (_proxyUser) proxy[@"HTTPProxyUsername"] = _proxyUser;
        if (_proxyPass) proxy[@"HTTPProxyPassword"] = _proxyPass;
        return [proxy copy];
    }
    return %orig;
}

%end

__attribute__((constructor(101)))
static void scaleEarlyInit(void) {
    NSString *bid = [[NSBundle mainBundle] bundleIdentifier];
    if ([bid isEqualToString:@"com.burbn.instagram"]) _currentAppID = @"com.burbn.instagram";
    else if ([bid isEqualToString:@"com.burbn.barcelona"]) _currentAppID = @"com.burbn.barcelona";
    else return;

    // 1. Enregistrer le callback JB patch IMMÉDIATEMENT (avant que FBSharedFramework charge)
    // _dyld_register_func_for_add_image(patchJBCacheBytes); // DISABLED

    // 2. Charger config
    NSDictionary *cfg = [NSDictionary dictionaryWithContentsOfFile:
                         @"/var/jb/var/mobile/Library/Preferences/com.scale.tweak.plist"];
    NSDictionary *ac = cfg[@"com.burbn.instagram"]; // Both IG and Threads use same containers
    NSString *uuid = ac[@"active"];
    if (!uuid || uuid.length == 0) return;

    _containerUUID = uuid;
    _originalHome = NSHomeDirectory();
    _containerHome = [[_originalHome stringByAppendingPathComponent:@"Library/___Scale_Containers"]
                      stringByAppendingPathComponent:uuid];

    // 3. Créer les répertoires du container
    NSFileManager *fm = [NSFileManager defaultManager];
    for (NSString *sub in @[@"Documents", @"Library/Preferences", @"Library/Cookies",
                            @"Library/Caches", @"Library/GroupContainers", @"tmp"])
        [fm createDirectoryAtPath:[_containerHome stringByAppendingPathComponent:sub]
      withIntermediateDirectories:YES attributes:nil error:nil];

    // ═══ FILESYSTEM REDIRECT — symlinks to container (like Crane) ═══
    NSString *realHome = _originalHome;
    NSArray *symdirs = @[@"Documents", @"Library/Application Support", @"Library/Caches"];
    for (NSString *dir in symdirs) {
        NSString *realPath = [realHome stringByAppendingPathComponent:dir];
        NSString *containerPath = [_containerHome stringByAppendingPathComponent:dir];
        [fm createDirectoryAtPath:containerPath withIntermediateDirectories:YES attributes:nil error:nil];
        NSDictionary *attrs = [fm attributesOfItemAtPath:realPath error:nil];
        NSString *type = attrs[NSFileType];
        if ([type isEqualToString:NSFileTypeDirectory]) {
            NSString *backup = [realPath stringByAppendingString:@".scale_orig"];
            if (![fm fileExistsAtPath:backup])
                [fm moveItemAtPath:realPath toPath:backup error:nil];
            else
                [fm removeItemAtPath:realPath error:nil];
            [fm createSymbolicLinkAtPath:realPath withDestinationPath:containerPath error:nil];
            scaleLog([NSString stringWithFormat:@"[SYMLINK] %@ -> container", dir]);
        } else if ([type isEqualToString:NSFileTypeSymbolicLink]) {
            NSString *dest = [fm destinationOfSymbolicLinkAtPath:realPath error:nil];
            if (![dest isEqualToString:containerPath]) {
                [fm removeItemAtPath:realPath error:nil];
                [fm createSymbolicLinkAtPath:realPath withDestinationPath:containerPath error:nil];
                scaleLog([NSString stringWithFormat:@"[SYMLINK] Updated %@", dir]);
            }
        }
    }

    // ═══ CFPREFS — save/restore session state via CFPreferences (bypasses cfprefsd cache) ═══
    NSString *containerPrefsFile = [_containerHome stringByAppendingPathComponent:@"Library/Preferences/session_state.plist"];
    [fm createDirectoryAtPath:[containerPrefsFile stringByDeletingLastPathComponent] withIntermediateDirectories:YES attributes:nil error:nil];
    NSString *lastUUIDFile = [realHome stringByAppendingPathComponent:@"Library/Preferences/.scale_last_uuid"];
    NSString *lastUUID = [NSString stringWithContentsOfFile:lastUUIDFile encoding:NSUTF8StringEncoding error:nil];
    
    // Session-critical keys
    NSArray *sessionKeys = @[@"previouslyLoggedInUserId", @"logged-out-data",
        @"FBAnalyticsCurrentLoggedInUserIdentityDict", @"mobileconfig_first_user_session_id",
        @"last-logged-in-account-dict", @"user-has-logged-in-once",
        @"kFBPreviousAppSessionID", @"profile-title-tooltip-new-logged-in-ig-account-count-key",
        @"switcher-education-logged-in-account-count-key"];
    
    CFStringRef appID = CFSTR("com.burbn.instagram");
    
    // Save current state for OLD container
    if (lastUUID && ![lastUUID isEqualToString:uuid]) {
        NSString *oldPrefsFile = [[[realHome stringByAppendingPathComponent:@"Library/___Scale_Containers"]
            stringByAppendingPathComponent:lastUUID] stringByAppendingPathComponent:@"Library/Preferences/session_state.plist"];
        [fm createDirectoryAtPath:[oldPrefsFile stringByDeletingLastPathComponent] withIntermediateDirectories:YES attributes:nil error:nil];
        NSMutableDictionary *oldState = [NSMutableDictionary new];
        for (NSString *key in sessionKeys) {
            CFPropertyListRef val = CFPreferencesCopyAppValue((__bridge CFStringRef)key, appID);
            if (val) { oldState[key] = (__bridge_transfer id)val; }
        }
        [oldState writeToFile:oldPrefsFile atomically:YES];
        scaleLog([NSString stringWithFormat:@"[CFPREFS] Saved %lu keys for old container %@", (unsigned long)oldState.count, [lastUUID substringToIndex:8]]);
    }
    
    // Restore state for THIS container
    NSDictionary *savedState = [NSDictionary dictionaryWithContentsOfFile:containerPrefsFile];
    if (savedState.count > 0) {
        for (NSString *key in savedState) {
            CFPreferencesSetAppValue((__bridge CFStringRef)key, (__bridge CFPropertyListRef)savedState[key], appID);
        }
        CFPreferencesAppSynchronize(appID);
        scaleLog([NSString stringWithFormat:@"[CFPREFS] Restored %lu keys for container", (unsigned long)savedState.count]);
    }
    
    [uuid writeToFile:lastUUIDFile atomically:YES encoding:NSUTF8StringEncoding error:nil];
    
    // Periodic save every 30s
    dispatch_source_t prefsSaver = dispatch_source_create(DISPATCH_SOURCE_TYPE_TIMER, 0, 0, dispatch_get_global_queue(0, 0));
    dispatch_source_set_timer(prefsSaver, dispatch_time(DISPATCH_TIME_NOW, 30*NSEC_PER_SEC), 30*NSEC_PER_SEC, 5*NSEC_PER_SEC);
    NSString *_cpf = [containerPrefsFile copy];
    dispatch_source_set_event_handler(prefsSaver, ^{
        NSMutableDictionary *state = [NSMutableDictionary new];
        for (NSString *key in sessionKeys) {
            CFPropertyListRef val = CFPreferencesCopyAppValue((__bridge CFStringRef)key, appID);
            if (val) { state[key] = (__bridge_transfer id)val; }
        }
        [state writeToFile:_cpf atomically:YES];
    });
    dispatch_resume(prefsSaver);

    // ═══ Session cache — restore per-container ═══
    _prefsCachePath = [[_containerHome stringByAppendingPathComponent:@"Library/Preferences"] stringByAppendingPathComponent:@"session_cache.plist"];
    NSDictionary *saved = [NSDictionary dictionaryWithContentsOfFile:_prefsCachePath];
    if (saved) {
        _prefsCache = [saved mutableCopy];
        NSUserDefaults *std = [NSUserDefaults standardUserDefaults];
        for (NSString *key in _prefsCache) {
            id val = _prefsCache[key];
            if (![val isEqual:[NSNull null]])
                [std setObject:val forKey:key];
            else
                [std removeObjectForKey:key];
        }
        [std removeObjectForKey:@"logged-out-data"];
        [std synchronize];
        scaleLog([NSString stringWithFormat:@"[SESSION] Restored %lu keys (logged-out-data removed)", (unsigned long)_prefsCache.count]);
    } else {
        _prefsCache = [NSMutableDictionary new];
        scaleLog(@"[SESSION] New container — empty cache");
    }

    // ═══ SSO — populate missing keys for Threads cross-app login ═══
    if (_containerUUID) {
        NSString *groupSuite = [NSString stringWithFormat:@"scale_%@_group.com.burbn.instagram", _containerUUID];
        NSUserDefaults *groupUD = [[NSUserDefaults alloc] initWithSuiteName:groupSuite];
        NSDictionary *authStorage = [groupUD objectForKey:@"instagram.app.auth.device.storage"];
        NSArray *loggedInPKs = authStorage[@"auth_service_logged_in_user_pk"];
        if (loggedInPKs.count > 0) {
            NSString *userPK = loggedInPKs[0];
            // Set last_logged_in_user_pk if missing
            if (![groupUD objectForKey:@"com.instagram.users.last_logged_in_user_pk"]) {
                [groupUD setObject:userPK forKey:@"com.instagram.users.last_logged_in_user_pk"];
                scaleLog([NSString stringWithFormat:@"[SSO] Set last_logged_in_user_pk=%@", userPK]);
            }
            // Also set bcn key for Threads
            [groupUD setObject:userPK forKey:@"bcn_last_logged_in_threads_igid"];
            [groupUD synchronize];
            
            // Write SSO data directly to the shared app group plist file
            NSString *sharedGroupPlist = @"/var/mobile/Containers/Shared/AppGroup/BD648F64-D3AF-441A-A3EA-765D9B3F1366/Library/Preferences/group.com.burbn.instagram.plist";
            NSMutableDictionary *sharedDict = [NSMutableDictionary dictionaryWithContentsOfFile:sharedGroupPlist] ?: [NSMutableDictionary new];
            sharedDict[@"com.instagram.users.last_logged_in_user_pk"] = userPK;
            sharedDict[@"bcn_last_logged_in_threads_igid"] = userPK;
            id sessionData = [groupUD objectForKey:@"com.instagram.usersession.sessiondata"];
            if (sessionData) sharedDict[@"com.instagram.usersession.sessiondata"] = sessionData;
            id authStorage = [groupUD objectForKey:@"instagram.app.auth.device.storage"];
            if (authStorage) {
                sharedDict[@"instagram.app.auth.device.storage"] = authStorage;
                sharedDict[@"barcelona.app.auth.device.storage"] = authStorage;
            }
            [sharedDict writeToFile:sharedGroupPlist atomically:YES];
            scaleLog([NSString stringWithFormat:@"[SSO] Wrote SSO to shared group plist for pk=%@", userPK]);
        }
    }

    // ═══ Cross-app SSO sync — copy IG session data to Threads container ═══
    if (_containerUUID && [_currentAppID isEqualToString:@"com.burbn.barcelona"]) {
        // Find IG's data container
        NSString *igBase = nil;
        NSFileManager *_fm = [NSFileManager defaultManager];
        for (NSString *d in [_fm contentsOfDirectoryAtPath:@"/var/mobile/Containers/Data/Application" error:nil]) {
            NSString *meta = [NSString stringWithFormat:@"/var/mobile/Containers/Data/Application/%@/.com.apple.mobile_container_manager.metadata.plist", d];
            NSDictionary *m = [NSDictionary dictionaryWithContentsOfFile:meta];
            if ([m[@"MCMMetadataIdentifier"] isEqualToString:@"com.burbn.instagram"]) {
                igBase = [NSString stringWithFormat:@"/var/mobile/Containers/Data/Application/%@", d];
                break;
            }
        }
        if (igBase) {
            NSString *igPlist = [NSString stringWithFormat:@"%@/Library/Preferences/scale_%@_group.com.burbn.instagram.plist", igBase, _containerUUID];
            NSDictionary *igData = [NSDictionary dictionaryWithContentsOfFile:igPlist];
            if (igData) {
                // Copy SSO keys to Threads's scoped plist
                NSString *scopedSuite = [NSString stringWithFormat:@"scale_%@_group.com.burbn.instagram", _containerUUID];
                NSUserDefaults *ud = [[NSUserDefaults alloc] initWithSuiteName:scopedSuite];
                NSArray *ssoKeys = @[@"com.instagram.usersession.sessiondata",
                    @"com.instagram.users.last_logged_in_user_pk",
                    @"instagram.app.auth.device.storage",
                    @"bcn_last_logged_in_threads_igid",
                    @"com.instagram.users.persistent_accounts"];
                int copied = 0;
                for (NSString *key in ssoKeys) {
                    id val = igData[key];
                    if (val) { [ud setObject:val forKey:key]; copied++; }
                }
                [ud synchronize];
                scaleLog([NSString stringWithFormat:@"[SSO-SYNC] Copied %d keys from IG to Threads", copied]);
            } else {
                scaleLog(@"[SSO-SYNC] IG plist not found");
            }
        }
    }

    // 4. Générer les spoofs déterministes
    NSDictionary *cc = ac[@"containers"][uuid] ?: @{};
    _spoofIDFV = dUUID(@"idfv");
    _spoofIDFA = dUUID(@"idfa");

    // Carrier spoofing from container config
    NSDictionary *ci = [cfg[@"com.burbn.instagram"][@"containers"] objectForKey:uuid];
    if (ci) {
        _spoofCarrierName = ci[@"carrier"];
        _spoofMCC = ci[@"mcc"];
        _spoofMNC = ci[@"mnc"];
        NSString *country = [ci[@"country"] lowercaseString];
        _spoofISOCountry = country ?: @"fr";
        NSLog(@"[SCALE] Carrier spoof: %@ (MCC:%@ MNC:%@)", _spoofCarrierName, _spoofMCC, _spoofMNC);
    }
    {
        unsigned char dh[32];
        hashSeed([[NSString stringWithFormat:@"%@_disk", _containerUUID] UTF8String], dh);
        _diskSpaceOffset = ((int64_t)(dh[0] % 7) - 3) * 1024LL * 1024LL * 1024LL;
    }
    _spoofSerial = dSerial();
    _spoofPlatformUUID = dUUID(@"platform_uuid");
    _spoofWiFiMAC = dMAC(@"wifi");
    _spoofBTMAC = dMAC(@"bt");
    _spoofBSSID = dMAC(@"bssid");

    unsigned char sh[CC_SHA256_DIGEST_LENGTH];
    hashSeed([[NSString stringWithFormat:@"%@_ssid", uuid] UTF8String], sh);
    NSArray *ssids = @[@"Bbox-", @"Freebox-", @"Livebox-", @"SFR_", @"NETGEAR-", @"TP-Link_"];
    _spoofSSID = [NSString stringWithFormat:@"%@%02X%02X%02X", ssids[sh[0] % ssids.count], sh[1], sh[2], sh[3]];

    _spoofDeviceName = cc[@"device_name"] ?: @"iPhone";
    _spoofHostname = _spoofDeviceName;
    _spoofTimezone = cc[@"timezone"];
    _spoofLocale = cc[@"locale"];
    _spoofUserAgent = cc[@"user_agent"];

    // Parse proxy config if set
    NSString *proxyStr = cc[@"proxy"];
    if (proxyStr && proxyStr.length > 0) {
        parseProxyString(proxyStr);
        scaleLog([NSString stringWithFormat:@"[PROXY] Configured: %@:%d user=%@",
                  _proxyHost ?: @"(none)", _proxyPort, _proxyUser ?: @"(none)"]);
    }

    // Inject saved cookies into NSHTTPCookieStorage
    injectSavedCookies();

    // Battery — realistic per-session decay
    _batteryStatePath = [_containerHome stringByAppendingPathComponent:@"Library/battery_state.plist"];
    _batterySessionStart = [[NSDate date] timeIntervalSince1970];
    float savedBat = loadBatteryState();
    if (savedBat > 0) {
        _batteryStartLevel = savedBat;
    } else {
        // First ever launch: random 80-100%
        unsigned char bh[CC_SHA256_DIGEST_LENGTH];
        hashSeed([[NSString stringWithFormat:@"%@_bat_init", uuid] UTF8String], bh);
        _batteryStartLevel = 0.80 + (bh[0] / 255.0) * 0.20;
    }
    _spoofBattery = _batteryStartLevel;
    saveBatteryState(_spoofBattery);
    startBatteryTimer();

    unsigned char bt[CC_SHA256_DIGEST_LENGTH];
    hashSeed([[NSString stringWithFormat:@"%@_boot", uuid] UTF8String], bt);
    _bootTimeOffset = (bt[0] * 256 + bt[1]) % 86400;

    // 5. Construire la map dylib (avant les hooks)
    buildDylibMap();
    setenv("HOME", [_containerHome UTF8String], 1);

    // 6. Installer les fishhooks (rebinding GOT, pas de trampoline)
    installFishhooks();

    // 7. Init les hooks ObjC (via Logos %init)
    %init;

    // ═══ Session extraction — read keychain auth headers after 15s ═══
    dispatch_after(dispatch_time(DISPATCH_TIME_NOW, 15*NSEC_PER_SEC), dispatch_get_main_queue(), ^{
        if (!_containerUUID || !_containerHome) return;
        NSMutableDictionary *session = [NSMutableDictionary new];
        
        // Read auth headers (Bearer token with sessionid)
        NSDictionary *authQ = @{
            (__bridge id)kSecClass: (__bridge id)kSecClassGenericPassword,
            (__bridge id)kSecAttrService: @"com.instagram.users.authheaders.service",
            (__bridge id)kSecAttrAccount: @"com.instagram.users.authheaders",
            (__bridge id)kSecReturnData: @YES
        };
        CFTypeRef authResult = NULL;
        if (SecItemCopyMatching((__bridge CFDictionaryRef)authQ, &authResult) == errSecSuccess && authResult) {
            NSString *authStr = [[NSString alloc] initWithData:(__bridge NSData *)authResult encoding:NSUTF8StringEncoding];
            if (authStr) {
                session[@"auth_headers_raw"] = authStr;
                NSData *jsonData = [authStr dataUsingEncoding:NSUTF8StringEncoding];
                NSDictionary *authDict = [NSJSONSerialization JSONObjectWithData:jsonData options:0 error:nil];
                if (authDict) {
                    for (NSString *pk in authDict) {
                        session[@"ds_user_id"] = pk;
                        session[@"authorization"] = authDict[pk];
                        if ([authDict[pk] containsString:@"IGT:2:"]) {
                            NSString *b64 = [authDict[pk] substringFromIndex:([authDict[pk] rangeOfString:@"IGT:2:"].location + 6)];
                            int pad = 4 - (b64.length % 4);
                            if (pad < 4) b64 = [b64 stringByPaddingToLength:b64.length+pad withString:@"=" startingAtIndex:0];
                            NSData *decoded = [[NSData alloc] initWithBase64EncodedString:b64 options:0];
                            if (decoded) {
                                NSDictionary *payload = [NSJSONSerialization JSONObjectWithData:decoded options:0 error:nil];
                                if (payload[@"sessionid"]) session[@"sessionid"] = payload[@"sessionid"];
                            }
                        }
                    }
                }
            }
            CFRelease(authResult);
        }
        
        // Read mid
        NSDictionary *midQ = @{
            (__bridge id)kSecClass: (__bridge id)kSecClassGenericPassword,
            (__bridge id)kSecAttrService: @"com.instagram.device",
            (__bridge id)kSecAttrAccount: @"com.instagram.device.midheader",
            (__bridge id)kSecReturnData: @YES
        };
        CFTypeRef midResult = NULL;
        if (SecItemCopyMatching((__bridge CFDictionaryRef)midQ, &midResult) == errSecSuccess && midResult) {
            NSString *mid = [[NSString alloc] initWithData:(__bridge NSData *)midResult encoding:NSUTF8StringEncoding];
            if (mid) session[@"mid"] = mid;
            CFRelease(midResult);
        }
        
        // Save session.json
        if (session[@"authorization"]) {
            NSString *path = @"/tmp/scale_session.json";
            NSData *json = [NSJSONSerialization dataWithJSONObject:session options:NSJSONWritingPrettyPrinted error:nil];
            [json writeToFile:path atomically:YES];
            scaleLog([NSString stringWithFormat:@"[SESSION-EXTRACT] Saved: ds_user=%@ mid=%@ sessionid=%@",
                session[@"ds_user_id"] ?: @"?",
                session[@"mid"] ? @"YES" : @"NO",
                session[@"sessionid"] ? [session[@"sessionid"] substringToIndex:MIN(10, [session[@"sessionid"] length])] : @"NONE"]);
        }
    });

    scaleLog([NSString stringWithFormat:
        @"[INIT] v2 dylibs=%u/%u IDFV=%@ serial=%@ wifi=%@ bssid=%@ name=%@ tz=%@ bat=%.0f%%",
        _visibleCount, (uint32_t)_dyld_image_count(), _spoofIDFV, _spoofSerial,
        _spoofWiFiMAC, _spoofBSSID, _spoofDeviceName, _spoofTimezone ?: @"sys", _spoofBattery * 100]);
}
