#import <Foundation/Foundation.h>

@interface ScaleContainerManager : NSObject

@property (nonatomic, strong) NSString *activeContainerUUID;
@property (nonatomic, strong) NSString *appBundleID;
@property (nonatomic, strong) NSDictionary *containerConfig;

+ (instancetype)sharedManager;

// Container management
- (NSString *)containerBasePath;
- (NSString *)activeContainerPath;
- (NSArray *)listContainers;
- (BOOL)switchToContainer:(NSString *)uuid;
- (NSString *)createContainerWithName:(NSString *)name;
- (BOOL)deleteContainer:(NSString *)uuid;
- (BOOL)wipeContainer:(NSString *)uuid;

// Config
- (void)loadConfig;
- (void)saveConfig;
- (NSDictionary *)configForContainer:(NSString *)uuid;
- (void)setConfig:(NSDictionary *)config forContainer:(NSString *)uuid;

// Paths
- (NSString *)redirectedPathForOriginal:(NSString *)originalPath;

@end
