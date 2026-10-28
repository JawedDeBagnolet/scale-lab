#import "ScaleContainerManager.h"

static NSString *const kScaleConfigPath = @"/var/jb/var/mobile/Library/Preferences/com.scale.tweak.plist";
static NSString *const kScaleContainersDir = @"Library/___Scale_Containers";

@implementation ScaleContainerManager

+ (instancetype)sharedManager {
    static ScaleContainerManager *instance;
    static dispatch_once_t onceToken;
    dispatch_once(&onceToken, ^{
        instance = [[ScaleContainerManager alloc] init];
        instance.appBundleID = [[NSBundle mainBundle] bundleIdentifier] ?: @"com.burbn.instagram";
        [instance loadConfig];
    });
    return instance;
}

#pragma mark - Config

- (void)loadConfig {
    NSDictionary *plist = [NSDictionary dictionaryWithContentsOfFile:kScaleConfigPath];
    if (!plist) {
        plist = @{};
    }
    NSDictionary *appConfig = plist[self.appBundleID];
    if (appConfig) {
        self.activeContainerUUID = appConfig[@"active"];
        self.containerConfig = appConfig[@"containers"] ?: @{};
    } else {
        self.activeContainerUUID = nil;
        self.containerConfig = @{};
    }
    NSLog(@"[ScaleTweak] Loaded config — active: %@, containers: %lu",
          self.activeContainerUUID ?: @"(default)", (unsigned long)self.containerConfig.count);
}

- (void)saveConfig {
    NSMutableDictionary *plist = [NSMutableDictionary dictionaryWithContentsOfFile:kScaleConfigPath] ?: [NSMutableDictionary new];
    plist[self.appBundleID] = @{
        @"active": self.activeContainerUUID ?: @"",
        @"containers": self.containerConfig ?: @{},
    };
    [plist writeToFile:kScaleConfigPath atomically:YES];
}

#pragma mark - Paths

- (NSString *)containerBasePath {
    // Get IG's real data container
    NSString *home = NSHomeDirectory();
    // Go up to the app's container root
    // // unused
    // IG stores in: /var/mobile/Containers/Data/Application/{UUID}/
    // We put containers in: {same}/{kScaleContainersDir}/{container_uuid}/
    return [home stringByAppendingPathComponent:kScaleContainersDir];
}

- (NSString *)activeContainerPath {
    if (!self.activeContainerUUID || [self.activeContainerUUID length] == 0) {
        return nil; // Use default (no redirect)
    }
    return [[self containerBasePath] stringByAppendingPathComponent:self.activeContainerUUID];
}

- (NSString *)redirectedPathForOriginal:(NSString *)originalPath {
    NSString *containerPath = [self activeContainerPath];
    if (!containerPath) return originalPath; // No active container = default behavior
    
    NSString *home = NSHomeDirectory();
    if ([originalPath hasPrefix:home]) {
        NSString *relative = [originalPath substringFromIndex:home.length];
        NSString *redirected = [containerPath stringByAppendingString:relative];
        return redirected;
    }
    return originalPath;
}

#pragma mark - Container Management

- (NSArray *)listContainers {
    NSMutableArray *result = [NSMutableArray new];
    NSString *basePath = [self containerBasePath];
    
    for (NSString *uuid in self.containerConfig) {
        NSDictionary *config = self.containerConfig[uuid];
        NSString *path = [basePath stringByAppendingPathComponent:uuid];
        BOOL exists = [[NSFileManager defaultManager] fileExistsAtPath:path];
        
        [result addObject:@{
            @"uuid": uuid,
            @"name": config[@"name"] ?: @"",
            @"exists": @(exists),
            @"active": @([uuid isEqualToString:self.activeContainerUUID ?: @""]),
        }];
    }
    return result;
}

- (NSString *)createContainerWithName:(NSString *)name {
    NSString *uuid = [[NSUUID UUID] UUIDString];
    NSString *path = [[self containerBasePath] stringByAppendingPathComponent:uuid];
    
    NSFileManager *fm = [NSFileManager defaultManager];
    NSError *error;
    
    // Create directory structure
    for (NSString *sub in @[@"Documents", @"Library/Preferences", @"Library/Cookies", @"Library/Caches", @"tmp"]) {
        [fm createDirectoryAtPath:[path stringByAppendingPathComponent:sub]
      withIntermediateDirectories:YES attributes:nil error:&error];
    }
    
    // Update config
    NSMutableDictionary *configs = [self.containerConfig mutableCopy] ?: [NSMutableDictionary new];
    configs[uuid] = @{
        @"name": name ?: @"",
        @"created_at": [[NSDate date] description],
    };
    self.containerConfig = configs;
    [self saveConfig];
    
    NSLog(@"[ScaleTweak] Created container '%@' -> %@", name, uuid);
    return uuid;
}

- (BOOL)switchToContainer:(NSString *)uuid {
    if (uuid && ![self.containerConfig objectForKey:uuid]) {
        NSLog(@"[ScaleTweak] Container %@ not found", uuid);
        return NO;
    }
    self.activeContainerUUID = uuid;
    [self saveConfig];
    NSLog(@"[ScaleTweak] Switched to container: %@", uuid ?: @"(default)");
    return YES;
}

- (BOOL)deleteContainer:(NSString *)uuid {
    NSString *path = [[self containerBasePath] stringByAppendingPathComponent:uuid];
    [[NSFileManager defaultManager] removeItemAtPath:path error:nil];
    
    NSMutableDictionary *configs = [self.containerConfig mutableCopy];
    [configs removeObjectForKey:uuid];
    self.containerConfig = configs;
    
    if ([uuid isEqualToString:self.activeContainerUUID]) {
        self.activeContainerUUID = nil;
    }
    [self saveConfig];
    NSLog(@"[ScaleTweak] Deleted container %@", uuid);
    return YES;
}

- (BOOL)wipeContainer:(NSString *)uuid {
    NSString *path = [[self containerBasePath] stringByAppendingPathComponent:uuid];
    [[NSFileManager defaultManager] removeItemAtPath:path error:nil];
    
    // Recreate empty structure
    NSFileManager *fm = [NSFileManager defaultManager];
    for (NSString *sub in @[@"Documents", @"Library/Preferences", @"Library/Cookies", @"Library/Caches", @"tmp"]) {
        [fm createDirectoryAtPath:[path stringByAppendingPathComponent:sub]
      withIntermediateDirectories:YES attributes:nil error:nil];
    }
    NSLog(@"[ScaleTweak] Wiped container %@", uuid);
    return YES;
}

- (NSDictionary *)configForContainer:(NSString *)uuid {
    return self.containerConfig[uuid] ?: @{};
}

- (void)setConfig:(NSDictionary *)config forContainer:(NSString *)uuid {
    NSMutableDictionary *configs = [self.containerConfig mutableCopy] ?: [NSMutableDictionary new];
    NSMutableDictionary *existing = [configs[uuid] mutableCopy] ?: [NSMutableDictionary new];
    [existing addEntriesFromDictionary:config];
    configs[uuid] = existing;
    self.containerConfig = configs;
    [self saveConfig];
}

@end
