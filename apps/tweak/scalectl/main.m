#import <Foundation/Foundation.h>
#include <CommonCrypto/CommonDigest.h>

static NSString *const kConfigPath = @"/var/jb/var/mobile/Library/Preferences/com.scale.tweak.plist";
static NSString *const kDefaultApp = @"com.burbn.instagram";

NSDictionary *loadConfig() {
    return [NSDictionary dictionaryWithContentsOfFile:kConfigPath] ?: @{};
}
void saveConfig(NSDictionary *config) {
    [(NSMutableDictionary *)config writeToFile:kConfigPath atomically:YES];
}

NSString *getIGContainerBase() {
    NSArray *dirs = [[NSFileManager defaultManager] contentsOfDirectoryAtPath:@"/var/mobile/Containers/Data/Application" error:nil];
    for (NSString *dir in dirs) {
        NSString *meta = [NSString stringWithFormat:@"/var/mobile/Containers/Data/Application/%@/.com.apple.mobile_container_manager.metadata.plist", dir];
        NSDictionary *m = [NSDictionary dictionaryWithContentsOfFile:meta];
        if ([m[@"MCMMetadataIdentifier"] isEqualToString:kDefaultApp])
            return [NSString stringWithFormat:@"/var/mobile/Containers/Data/Application/%@", dir];
    }
    return nil;
}

NSString *containerPath(NSString *uuid) {
    NSString *base = getIGContainerBase();
    return base ? [NSString stringWithFormat:@"%@/Library/___Scale_Containers/%@", base, uuid] : nil;
}

// Geo profiles by country code
NSDictionary *geoProfile(NSString *country, NSString *uuid) {
    // Hash uuid for deterministic random selections
    unsigned char h[CC_SHA256_DIGEST_LENGTH];
    const char *s = [uuid UTF8String];
    CC_SHA256(s, (CC_LONG)strlen(s), h);
    
    NSDictionary *profiles = @{
        @"FR": @{
            @"timezone": @"Europe/Paris",
            @"locale": @"fr_FR",
            @"mcc": @"208",
            @"carriers": @[
                @{@"name":@"Free",@"mnc":@"15"},
                @{@"name":@"Orange",@"mnc":@"01"},
                @{@"name":@"SFR",@"mnc":@"10"},
                @{@"name":@"Bouygues",@"mnc":@"20"},
            ],
        },
        @"US": @{
            @"timezone": @"America/New_York",
            @"locale": @"en_US",
            @"mcc": @"310",
            @"carriers": @[
                @{@"name":@"T-Mobile",@"mnc":@"260"},
                @{@"name":@"AT&T",@"mnc":@"410"},
                @{@"name":@"Verizon",@"mnc":@"004"},
            ],
        },
        @"BR": @{
            @"timezone": @"America/Sao_Paulo",
            @"locale": @"pt_BR",
            @"mcc": @"724",
            @"carriers": @[
                @{@"name":@"Claro",@"mnc":@"05"},
                @{@"name":@"Vivo",@"mnc":@"06"},
                @{@"name":@"TIM",@"mnc":@"04"},
            ],
        },
        @"ES": @{
            @"timezone": @"Europe/Madrid",
            @"locale": @"es_ES",
            @"mcc": @"214",
            @"carriers": @[
                @{@"name":@"Movistar",@"mnc":@"07"},
                @{@"name":@"Vodafone",@"mnc":@"01"},
                @{@"name":@"Orange",@"mnc":@"03"},
            ],
        },
        @"IT": @{
            @"timezone": @"Europe/Rome",
            @"locale": @"it_IT",
            @"mcc": @"222",
            @"carriers": @[
                @{@"name":@"TIM",@"mnc":@"01"},
                @{@"name":@"Vodafone",@"mnc":@"10"},
                @{@"name":@"Wind Tre",@"mnc":@"88"},
            ],
        },
        @"GB": @{
            @"timezone": @"Europe/London",
            @"locale": @"en_GB",
            @"mcc": @"234",
            @"carriers": @[
                @{@"name":@"EE",@"mnc":@"30"},
                @{@"name":@"Vodafone",@"mnc":@"15"},
                @{@"name":@"Three",@"mnc":@"20"},
            ],
        },
        @"DE": @{
            @"timezone": @"Europe/Berlin",
            @"locale": @"de_DE",
            @"mcc": @"262",
            @"carriers": @[
                @{@"name":@"Telekom",@"mnc":@"01"},
                @{@"name":@"Vodafone",@"mnc":@"02"},
                @{@"name":@"O2",@"mnc":@"07"},
            ],
        },
    };
    
    NSDictionary *prof = profiles[country] ?: profiles[@"FR"];
    NSArray *carriers = prof[@"carriers"];
    NSDictionary *carrier = carriers[h[0] % carriers.count];
    
    return @{
        @"timezone": prof[@"timezone"],
        @"locale": prof[@"locale"],
        @"mcc": prof[@"mcc"],
        @"mnc": carrier[@"mnc"],
        @"carrier": carrier[@"name"],
    };
}

// French first names for device names
NSString *randomDeviceName(NSString *uuid) {
    unsigned char h[CC_SHA256_DIGEST_LENGTH];
    const char *s = [[uuid stringByAppendingString:@"_devname"] UTF8String];
    CC_SHA256(s, (CC_LONG)strlen(s), h);
    
    NSArray *names = @[@"Lea",@"Emma",@"Chloe",@"Manon",@"Camille",@"Lucas",@"Hugo",@"Nathan",@"Louis",@"Jade",
        @"Louise",@"Alice",@"Lina",@"Rose",@"Anna",@"Jules",@"Arthur",@"Leo",@"Gabriel",@"Raphael",
        @"Mia",@"Zoe",@"Ines",@"Clara",@"Sarah",@"Tom",@"Adam",@"Noah",@"Ethan",@"Liam"];
    NSArray *formats = @[@"iPhone de %@", @"iPhone de %@", @"iPhone %@", @"%@'s iPhone"];
    
    NSString *name = names[h[0] % names.count];
    NSString *fmt = formats[h[1] % formats.count];
    return [NSString stringWithFormat:fmt, name];
}

// ═══ Commands ═══

void listContainers(NSString *appId) {
    NSDictionary *config = loadConfig();
    NSDictionary *ac = config[appId] ?: @{};
    NSString *active = ac[@"active"] ?: @"";
    NSDictionary *containers = ac[@"containers"] ?: @{};
    printf("App: %s | Active: %s | %lu containers\n\n",
        [appId UTF8String], active.length ? [active UTF8String] : "(default)", (unsigned long)containers.count);
    for (NSString *uuid in containers) {
        NSDictionary *c = containers[uuid];
        BOOL on = [uuid isEqualToString:active];
        printf("  %s %-20s %s %s%s\n",
            on ? ">" : " ",
            [c[@"name"] UTF8String] ?: "?",
            [[uuid substringToIndex:MIN((NSUInteger)8, uuid.length)] UTF8String],
            on ? "[ACTIVE]" : "",
            c[@"carrier"] ? [[NSString stringWithFormat:@"  %@ %@", c[@"carrier"], c[@"timezone"]] UTF8String] : "");
    }
}

void switchContainer(NSString *appId, NSString *target) {
    NSMutableDictionary *config = [loadConfig() mutableCopy] ?: [NSMutableDictionary new];
    NSMutableDictionary *ac = [config[appId] mutableCopy] ?: [NSMutableDictionary new];
    NSDictionary *containers = ac[@"containers"] ?: @{};
    
    if ([target isEqualToString:@"default"]) {
        ac[@"active"] = @""; config[appId] = ac; saveConfig(config);
        printf("Switched to default\n"); return;
    }
    NSString *uuid = nil;
    if ([target hasPrefix:@"name:"]) {
        NSString *n = [target substringFromIndex:5];
        for (NSString *u in containers)
            if ([containers[u][@"name"] isEqualToString:n]) { uuid = u; break; }
    } else uuid = target;
    if (!uuid || !containers[uuid]) { printf("Not found: %s\n", [target UTF8String]); return; }
    ac[@"active"] = uuid; config[appId] = ac; saveConfig(config);
    printf("Switched to: %s\n", [containers[uuid][@"name"] UTF8String] ?: "?");
}

void createContainer(NSString *appId, NSString *name, NSString *country, NSString *persona) {
    NSMutableDictionary *config = [loadConfig() mutableCopy] ?: [NSMutableDictionary new];
    NSMutableDictionary *ac = [config[appId] mutableCopy] ?: [NSMutableDictionary new];
    NSMutableDictionary *containers = [ac[@"containers"] mutableCopy] ?: [NSMutableDictionary new];
    
    NSString *uuid = [[NSUUID UUID] UUIDString];
    NSDictionary *geo = geoProfile(country ?: @"FR", uuid);
    NSString *devName;
    if (persona && persona.length > 0) {
        devName = [NSString stringWithFormat:@"iPhone de %@", persona];
    } else {
        devName = randomDeviceName(uuid);
    }
    
    NSMutableDictionary *c = [NSMutableDictionary new];
    c[@"name"] = name;
    c[@"created_at"] = [[NSDate date] description];
    c[@"country"] = country ?: @"FR";
    c[@"device_name"] = devName;
    c[@"timezone"] = geo[@"timezone"];
    c[@"locale"] = geo[@"locale"];
    c[@"carrier"] = geo[@"carrier"];
    c[@"mcc"] = geo[@"mcc"];
    c[@"mnc"] = geo[@"mnc"];
    
    containers[uuid] = c;
    ac[@"containers"] = containers;
    config[appId] = ac;
    saveConfig(config);
    
    NSString *path = containerPath(uuid);
    if (path) {
        NSFileManager *fm = [NSFileManager defaultManager];
        for (NSString *sub in @[@"Documents",@"Library/Preferences",@"Library/Cookies",@"Library/Caches",@"Library/GroupContainers",@"tmp"])
            [fm createDirectoryAtPath:[path stringByAppendingPathComponent:sub] withIntermediateDirectories:YES attributes:nil error:nil];
    }
    
    printf("Created: %s -> %s\n", [name UTF8String], [[uuid substringToIndex:8] UTF8String]);
    printf("  Device:   %s\n", [devName UTF8String]);
    printf("  Country:  %s\n", [country ?: @"FR" UTF8String]);
    printf("  Timezone: %s\n", [geo[@"timezone"] UTF8String]);
    printf("  Carrier:  %s (MCC:%s MNC:%s)\n", [geo[@"carrier"] UTF8String], [geo[@"mcc"] UTF8String], [geo[@"mnc"] UTF8String]);
    printf("  Locale:   %s\n", [geo[@"locale"] UTF8String]);
}

void deleteContainer(NSString *appId, NSString *uuid) {
    NSMutableDictionary *config = [loadConfig() mutableCopy];
    NSMutableDictionary *ac = [config[appId] mutableCopy];
    NSMutableDictionary *containers = [ac[@"containers"] mutableCopy];
    if (!containers[uuid]) { printf("Not found\n"); return; }
    [containers removeObjectForKey:uuid];
    if ([ac[@"active"] isEqualToString:uuid]) ac[@"active"] = @"";
    ac[@"containers"] = containers; config[appId] = ac; saveConfig(config);
    NSString *path = containerPath(uuid);
    if (path) [[NSFileManager defaultManager] removeItemAtPath:path error:nil];
    printf("Deleted\n");
}

void wipeContainer(NSString *appId, NSString *uuid) {
    NSMutableDictionary *config = [loadConfig() mutableCopy];
    NSMutableDictionary *ac = [config[appId] mutableCopy];
    NSDictionary *containers = ac[@"containers"] ?: @{};
    if (!containers[uuid]) { printf("Not found: %s\n", [uuid UTF8String]); return; }

    NSString *path = containerPath(uuid);
    if (!path) { printf("ERROR: IG container base not found\n"); return; }

    NSString *name = containers[uuid][@"name"] ?: @"?";

    // Remove container data but keep directory structure and config
    [[NSFileManager defaultManager] removeItemAtPath:path error:nil];
    NSFileManager *fm = [NSFileManager defaultManager];
    for (NSString *sub in @[@"Documents",@"Library/Preferences",@"Library/Cookies",@"Library/Caches",@"Library/GroupContainers",@"tmp"])
        [fm createDirectoryAtPath:[path stringByAppendingPathComponent:sub] withIntermediateDirectories:YES attributes:nil error:nil];

    printf("Wiped container: %s (%s)\n", [name UTF8String],
        [[uuid substringToIndex:MIN((NSUInteger)8, uuid.length)] UTF8String]);
    printf("  Config preserved, data cleared. App restart required.\n");
}

void exportContainer(NSString *appId, NSString *uuid, NSString *outPath) {
    NSDictionary *config = loadConfig();
    NSDictionary *ac = config[appId] ?: @{};
    NSDictionary *containers = ac[@"containers"] ?: @{};
    NSDictionary *cc = containers[uuid];
    if (!cc) { printf("Not found: %s\n", [uuid UTF8String]); return; }

    NSString *path = containerPath(uuid);
    if (!path) { printf("ERROR: IG container base not found\n"); return; }

    NSMutableDictionary *result = [NSMutableDictionary new];

    // Container config
    result[@"container"] = @{
        @"uuid": uuid,
        @"name": cc[@"name"] ?: @"",
        @"country": cc[@"country"] ?: @"",
        @"device_name": cc[@"device_name"] ?: @"",
        @"timezone": cc[@"timezone"] ?: @"",
        @"locale": cc[@"locale"] ?: @"",
        @"carrier": cc[@"carrier"] ?: @"",
        @"mcc": cc[@"mcc"] ?: @"",
        @"mnc": cc[@"mnc"] ?: @"",
        @"proxy": cc[@"proxy"] ?: [NSNull null],
        @"created_at": cc[@"created_at"] ?: @"",
    };

    // Session data from session.json
    NSString *sessionPath = [path stringByAppendingPathComponent:@"Library/session.json"];
    NSData *sessionData = [NSData dataWithContentsOfFile:sessionPath];
    if (sessionData) {
        NSDictionary *session = [NSJSONSerialization JSONObjectWithData:sessionData options:0 error:nil];
        if (session) result[@"session"] = session;
    }

    // Cookies
    NSString *cookiePath = [path stringByAppendingPathComponent:@"Library/Cookies/scale_cookies.dat"];
    NSData *cookieData = [NSData dataWithContentsOfFile:cookiePath];
    if (cookieData) {
        @try {
            NSError *archiveErr = nil;
            NSSet *classes = [NSSet setWithArray:@[[NSArray class],[NSHTTPCookie class],[NSDictionary class],[NSString class],[NSNumber class],[NSDate class]]];
            NSArray *cookies = [NSKeyedUnarchiver unarchivedObjectOfClasses:classes fromData:cookieData error:&archiveErr];
            if ([cookies isKindOfClass:[NSArray class]]) {
                NSMutableDictionary *cookieDict = [NSMutableDictionary new];
                for (NSHTTPCookie *c in cookies) {
                    if ([c isKindOfClass:[NSHTTPCookie class]])
                        cookieDict[c.name] = c.value;
                }
                result[@"cookies"] = cookieDict;
            }
        } @catch (NSException *e) {}
    }

    // Preferences snapshot
    NSString *prefsPath = [[path stringByAppendingPathComponent:@"Library/Preferences"]
                           stringByAppendingPathComponent:@"com.burbn.instagram.plist"];
    NSDictionary *prefs = [NSDictionary dictionaryWithContentsOfFile:prefsPath];
    if (prefs) {
        NSMutableDictionary *fp = [NSMutableDictionary new];
        for (NSString *key in prefs) {
            if ([key containsString:@"device_id"] || [key containsString:@"family_device_id"]
                || [key containsString:@"user_agent"] || [key containsString:@"FamilyDevice"]) {
                fp[key] = prefs[key];
            }
        }
        if (fp.count > 0) result[@"fingerprint"] = fp;
    }

    // Battery state
    NSString *batPath = [path stringByAppendingPathComponent:@"Library/battery_state.plist"];
    NSDictionary *bat = [NSDictionary dictionaryWithContentsOfFile:batPath];
    if (bat) result[@"battery"] = bat;

    // Write output
    NSData *json = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    if (!json) { printf("ERROR: JSON serialization failed\n"); return; }
    [json writeToFile:outPath atomically:YES];
    printf("Exported to: %s\n", [outPath UTF8String]);
    printf("  Container: %s\n", [cc[@"name"] UTF8String] ?: "?");
    printf("  Session:   %s\n", result[@"session"] ? "YES" : "NO");
    printf("  Cookies:   %s\n", result[@"cookies"] ? "YES" : "NO");
    printf("  FP keys:   %lu\n", (unsigned long)[result[@"fingerprint"] count]);
}

void injectFromFile(NSString *appId, NSString *uuid, NSString *jsonPath) {
    NSString *path = containerPath(uuid);
    if (!path) { printf("ERROR: IG container not found\n"); return; }
    NSData *data = [NSData dataWithContentsOfFile:jsonPath];
    if (!data) { printf("ERROR: Cannot read %s\n", [jsonPath UTF8String]); return; }
    NSDictionary *json = [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    if (!json) { printf("ERROR: Invalid JSON\n"); return; }
    
    NSDictionary *session = json[@"session"];
    if (session) {
        printf("Injecting cookies...\n");
        NSString *cookieDir = [path stringByAppendingPathComponent:@"Library/Cookies"];
        [[NSFileManager defaultManager] createDirectoryAtPath:cookieDir withIntermediateDirectories:YES attributes:nil error:nil];
        NSMutableArray *cookies = [NSMutableArray new];
        NSDictionary *fields = @{@"sessionid":session[@"sessionid"]?:@"",@"csrftoken":session[@"csrftoken"]?:@"",
            @"ds_user_id":session[@"ds_user_id"]?:@"",@"mid":session[@"mid"]?:@"",@"ig_did":session[@"ig_did"]?:@""};
        for (NSString *n in fields) {
            if ([fields[n] length] == 0) continue;
            NSHTTPCookie *ck = [NSHTTPCookie cookieWithProperties:@{
                NSHTTPCookieName:n, NSHTTPCookieValue:fields[n], NSHTTPCookieDomain:@".instagram.com",
                NSHTTPCookiePath:@"/", NSHTTPCookieExpires:[NSDate dateWithTimeIntervalSinceNow:365*86400]}];
            if (ck) [cookies addObject:ck];
        }
        NSData *cd = [NSKeyedArchiver archivedDataWithRootObject:cookies requiringSecureCoding:NO error:nil];
        [cd writeToFile:[cookieDir stringByAppendingPathComponent:@"scale_cookies.dat"] atomically:YES];
        printf("  %lu cookies\n", (unsigned long)cookies.count);
    }
    
    NSDictionary *fp = json[@"fingerprint"];
    if (fp) {
        printf("Injecting device IDs...\n");
        NSString *pp = [[path stringByAppendingPathComponent:@"Library/Preferences"] stringByAppendingPathComponent:@"com.burbn.instagram.plist"];
        NSMutableDictionary *plist = [NSMutableDictionary dictionaryWithContentsOfFile:pp] ?: [NSMutableDictionary new];
        NSString *uid = session[@"ds_user_id"] ?: @"0";
        NSString *did = fp[@"device_id"] ?: [[NSUUID UUID] UUIDString];
        NSString *fid = fp[@"family_device_id"] ?: [[NSUUID UUID] UUIDString];
        for (NSString *pfx in @[[NSString stringWithFormat:@"crypto_db_%@.db_",uid],
                                [NSString stringWithFormat:@"ig-msys-%@.db_",uid],
                                [NSString stringWithFormat:@"incoming_db_%@.db_",uid],
                                [NSString stringWithFormat:@"reverb_db_%@.db_",uid]]) {
            plist[[pfx stringByAppendingString:@"device_id"]] = did;
            plist[[pfx stringByAppendingString:@"family_device_id"]] = fid;
        }
        plist[@"com.facebook.familydeviceid.backup.vendordeviceid"] = fid;
        plist[@"kFBFamilyDeviceIDBackupKey"] = fid;
        if (fp[@"user_agent"]) plist[@"scale_user_agent"] = fp[@"user_agent"];
        [plist writeToFile:pp atomically:YES];
        printf("  device_id=%s\n", [[did substringToIndex:8] UTF8String]);
    }
    
    if (json[@"proxy"]) {
        NSMutableDictionary *config = [loadConfig() mutableCopy];
        NSMutableDictionary *ac = [config[appId] mutableCopy];
        NSMutableDictionary *cs = [ac[@"containers"] mutableCopy];
        NSMutableDictionary *cc = [cs[uuid] mutableCopy];
        cc[@"proxy"] = json[@"proxy"];
        cs[uuid] = cc; ac[@"containers"] = cs; config[appId] = ac; saveConfig(config);
        printf("  proxy=%s\n", [json[@"proxy"] UTF8String]);
    }
    printf("Done\n");
}

void printUsage() {
    printf("scalectl — ScaleTweak CLI\n\n");
    printf("  --list [app-id]                          List containers\n");
    printf("  --create <app-id> <name> [country] [persona]  Create (country: FR,US,BR,ES,IT,GB,DE)\n");
    printf("  --switch <app-id> <uuid|name:N|default>  Switch\n");
    printf("  --delete <app-id> <uuid>                 Delete\n");
    printf("  --inject <app-id> <uuid> <file.json>     Inject session+fingerprint\n");
    printf("  --wipe   <app-id> <uuid>                 Wipe data, keep config\n");
    printf("  --export <app-id> <uuid> <out.json>      Export session+cookies+config\n");
    printf("  --status                                 Status\n");
}

void printStatus() {
    NSDictionary *config = loadConfig();
    NSString *base = getIGContainerBase();
    printf("ScaleTweak Status\n  IG: %s\n", base ? [base UTF8String] : "NOT FOUND");
    for (NSString *appId in config) {
        NSDictionary *ac = config[appId];
        if (![ac isKindOfClass:[NSDictionary class]]) continue;
        printf("  %s: %lu containers, active=%s\n", [appId UTF8String],
            (unsigned long)[ac[@"containers"] count], [ac[@"active"] UTF8String] ?: "default");
    }
}

int main(int argc, char *argv[]) {
    @autoreleasepool {
        if (argc < 2) { printUsage(); return 0; }
        NSString *cmd = [NSString stringWithUTF8String:argv[1]];
        NSString *appId = argc > 2 ? [NSString stringWithUTF8String:argv[2]] : kDefaultApp;
        
        if ([cmd isEqualToString:@"--list"]) listContainers(appId);
        else if ([cmd isEqualToString:@"--create"] && argc > 3) {
            NSString *country = argc > 4 ? [NSString stringWithUTF8String:argv[4]] : @"FR";
            NSString *persona = argc > 5 ? [NSString stringWithUTF8String:argv[5]] : nil;
            createContainer(appId, [NSString stringWithUTF8String:argv[3]], country, persona);
        }
        else if ([cmd isEqualToString:@"--switch"] && argc > 3) switchContainer(appId, [NSString stringWithUTF8String:argv[3]]);
        else if ([cmd isEqualToString:@"--delete"] && argc > 3) deleteContainer(appId, [NSString stringWithUTF8String:argv[3]]);
        else if ([cmd isEqualToString:@"--inject"] && argc > 4) injectFromFile(appId, [NSString stringWithUTF8String:argv[3]], [NSString stringWithUTF8String:argv[4]]);
        else if ([cmd isEqualToString:@"--wipe"] && argc > 3) wipeContainer(appId, [NSString stringWithUTF8String:argv[3]]);
        else if ([cmd isEqualToString:@"--export"] && argc > 4) exportContainer(appId, [NSString stringWithUTF8String:argv[3]], [NSString stringWithUTF8String:argv[4]]);
        else if ([cmd isEqualToString:@"--status"]) printStatus();
        else printUsage();
        return 0;
    }
}
