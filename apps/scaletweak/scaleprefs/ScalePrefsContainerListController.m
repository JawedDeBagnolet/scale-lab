#import "ScalePrefsContainerListController.h"

static NSString *const kConfigPath = @"/var/jb/var/mobile/Library/Preferences/com.scale.tweak.plist";
static NSString *const kDefaultApp = @"com.burbn.instagram";

@interface ScalePrefsContainerListController ()
@property (nonatomic, strong) NSMutableArray<NSString *> *sortedUUIDs;
@property (nonatomic, strong) NSMutableDictionary *config;
@end

@implementation ScalePrefsContainerListController

#pragma mark - Config I/O

- (NSDictionary *)loadConfig {
    return [NSDictionary dictionaryWithContentsOfFile:kConfigPath] ?: @{};
}

- (void)saveConfig:(NSDictionary *)config {
    [config writeToFile:kConfigPath atomically:YES];
}

- (NSDictionary *)containers {
    return self.config[kDefaultApp][@"containers"] ?: @{};
}

- (NSString *)activeUUID {
    return self.config[kDefaultApp][@"active"] ?: @"";
}

- (NSArray<NSString *> *)orderArray {
    return self.config[kDefaultApp][@"container_order"] ?: @[];
}

#pragma mark - Sorting

- (void)rebuildSortedUUIDs {
    NSDictionary *containers = [self containers];
    NSArray *savedOrder = [self orderArray];

    if (savedOrder.count > 0) {
        // Use saved order, append any new containers at the end sorted by created_at
        NSMutableArray *ordered = [NSMutableArray new];
        NSMutableSet *seen = [NSMutableSet new];

        for (NSString *uuid in savedOrder) {
            if (containers[uuid]) {
                [ordered addObject:uuid];
                [seen addObject:uuid];
            }
        }

        // New containers not yet in the saved order — sorted by created_at, appended at bottom
        NSMutableArray *unseen = [NSMutableArray new];
        for (NSString *uuid in containers) {
            if (![seen containsObject:uuid]) [unseen addObject:uuid];
        }
        [unseen sortUsingComparator:^NSComparisonResult(NSString *a, NSString *b) {
            NSString *da = containers[a][@"created_at"] ?: @"";
            NSString *db = containers[b][@"created_at"] ?: @"";
            return [da compare:db];
        }];
        [ordered addObjectsFromArray:unseen];

        self.sortedUUIDs = ordered;
    } else {
        // No saved order — sort all by created_at (oldest first, newest at bottom)
        NSMutableArray *all = [[containers allKeys] mutableCopy];
        [all sortUsingComparator:^NSComparisonResult(NSString *a, NSString *b) {
            NSString *da = containers[a][@"created_at"] ?: @"";
            NSString *db = containers[b][@"created_at"] ?: @"";
            return [da compare:db];
        }];
        self.sortedUUIDs = all;
    }
}

- (void)persistOrder {
    NSMutableDictionary *config = [self.config mutableCopy];
    NSMutableDictionary *ac = [config[kDefaultApp] mutableCopy];
    ac[@"container_order"] = [self.sortedUUIDs copy];
    config[kDefaultApp] = ac;
    self.config = config;
    [self saveConfig:config];
}

#pragma mark - Lifecycle

- (void)viewDidLoad {
    [super viewDidLoad];
    self.title = @"Containers";
    self.navigationItem.rightBarButtonItem = self.editButtonItem;

    self.config = [[self loadConfig] mutableCopy];
    [self rebuildSortedUUIDs];
}

- (void)viewWillAppear:(BOOL)animated {
    [super viewWillAppear:animated];
    self.config = [[self loadConfig] mutableCopy];
    [self rebuildSortedUUIDs];
    [self.tableView reloadData];
}

#pragma mark - UITableViewDataSource

- (NSInteger)numberOfSectionsInTableView:(UITableView *)tv { return 1; }

- (NSInteger)tableView:(UITableView *)tv numberOfRowsInSection:(NSInteger)s {
    return self.sortedUUIDs.count;
}

- (UITableViewCell *)tableView:(UITableView *)tv cellForRowAtIndexPath:(NSIndexPath *)ip {
    static NSString *rid = @"ContainerCell";
    UITableViewCell *cell = [tv dequeueReusableCellWithIdentifier:rid];
    if (!cell) cell = [[UITableViewCell alloc] initWithStyle:UITableViewCellStyleSubtitle reuseIdentifier:rid];

    NSString *uuid = self.sortedUUIDs[ip.row];
    NSDictionary *c = [self containers][uuid];
    BOOL isActive = [uuid isEqualToString:[self activeUUID]];

    cell.textLabel.text = [NSString stringWithFormat:@"%@%@", c[@"name"] ?: @"?", isActive ? @"  ★" : @""];
    cell.textLabel.font = [UIFont systemFontOfSize:16 weight:isActive ? UIFontWeightSemibold : UIFontWeightRegular];

    NSString *country = c[@"country"] ?: @"";
    NSString *carrier = c[@"carrier"] ?: @"";
    NSString *shortUUID = [uuid substringToIndex:MIN((NSUInteger)8, uuid.length)];
    cell.detailTextLabel.text = [NSString stringWithFormat:@"%@ · %@ · %@", country, carrier, shortUUID];
    cell.detailTextLabel.textColor = [UIColor secondaryLabelColor];

    cell.showsReorderControl = YES;
    return cell;
}

- (NSString *)tableView:(UITableView *)tv titleForHeaderInSection:(NSInteger)s {
    return [NSString stringWithFormat:@"%lu containers", (unsigned long)self.sortedUUIDs.count];
}

#pragma mark - Reorder

- (BOOL)tableView:(UITableView *)tv canMoveRowAtIndexPath:(NSIndexPath *)ip { return YES; }

- (void)tableView:(UITableView *)tv moveRowAtIndexPath:(NSIndexPath *)from toIndexPath:(NSIndexPath *)to {
    NSString *uuid = self.sortedUUIDs[from.row];
    [self.sortedUUIDs removeObjectAtIndex:from.row];
    [self.sortedUUIDs insertObject:uuid atIndex:to.row];
    [self persistOrder];
}

#pragma mark - Delete

- (BOOL)tableView:(UITableView *)tv canEditRowAtIndexPath:(NSIndexPath *)ip { return YES; }

- (UITableViewCellEditingStyle)tableView:(UITableView *)tv editingStyleForRowAtIndexPath:(NSIndexPath *)ip {
    return UITableViewCellEditingStyleDelete;
}

- (void)tableView:(UITableView *)tv commitEditingStyle:(UITableViewCellEditingStyle)style forRowAtIndexPath:(NSIndexPath *)ip {
    if (style != UITableViewCellEditingStyleDelete) return;

    NSString *uuid = self.sortedUUIDs[ip.row];
    NSDictionary *c = [self containers][uuid];
    NSString *name = c[@"name"] ?: @"?";
    BOOL isActive = [uuid isEqualToString:[self activeUUID]];

    NSString *msg = isActive
        ? [NSString stringWithFormat:@"Delete \"%@\"?\nThis is the active container. The app will revert to default.", name]
        : [NSString stringWithFormat:@"Delete \"%@\"?\nAll container data will be removed.", name];

    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Delete Container"
                                                                  message:msg
                                                           preferredStyle:UIAlertControllerStyleAlert];

    [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Delete" style:UIAlertActionStyleDestructive handler:^(UIAlertAction *a) {
        [self deleteContainerAtIndex:ip.row uuid:uuid];
    }]];

    [self presentViewController:alert animated:YES completion:nil];
}

- (void)deleteContainerAtIndex:(NSInteger)idx uuid:(NSString *)uuid {
    // Remove container data directory
    // Find IG container base
    NSString *igBase = nil;
    NSArray *appContainers = [[NSFileManager defaultManager]
        contentsOfDirectoryAtPath:@"/var/mobile/Containers/Data/Application" error:nil];
    for (NSString *dir in appContainers) {
        NSString *full = [@"/var/mobile/Containers/Data/Application" stringByAppendingPathComponent:dir];
        NSString *meta = [full stringByAppendingPathComponent:@".com.apple.mobile_container_manager.metadata.plist"];
        NSDictionary *md = [NSDictionary dictionaryWithContentsOfFile:meta];
        if ([md[@"MCMMetadataIdentifier"] isEqualToString:kDefaultApp]) { igBase = full; break; }
    }

    if (igBase) {
        NSString *containerPath = [[igBase stringByAppendingPathComponent:@"Library/___Scale_Containers"]
                                    stringByAppendingPathComponent:uuid];
        [[NSFileManager defaultManager] removeItemAtPath:containerPath error:nil];
    }

    // Remove from config
    NSMutableDictionary *config = [self.config mutableCopy];
    NSMutableDictionary *ac = [config[kDefaultApp] mutableCopy];
    NSMutableDictionary *cs = [ac[@"containers"] mutableCopy];
    [cs removeObjectForKey:uuid];
    ac[@"containers"] = cs;

    // If active, clear
    if ([ac[@"active"] isEqualToString:uuid]) ac[@"active"] = @"";

    config[kDefaultApp] = ac;
    self.config = config;
    [self saveConfig:config];

    [self.sortedUUIDs removeObjectAtIndex:idx];
    [self persistOrder];

    [self.tableView deleteRowsAtIndexPaths:@[[NSIndexPath indexPathForRow:idx inSection:0]]
                          withRowAnimation:UITableViewRowAnimationAutomatic];
}

#pragma mark - Select (switch active)

- (void)tableView:(UITableView *)tv didSelectRowAtIndexPath:(NSIndexPath *)ip {
    [tv deselectRowAtIndexPath:ip animated:YES];

    NSString *uuid = self.sortedUUIDs[ip.row];
    NSDictionary *c = [self containers][uuid];
    NSString *name = c[@"name"] ?: @"?";

    if ([uuid isEqualToString:[self activeUUID]]) return; // already active

    UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Switch Container"
                                                                  message:[NSString stringWithFormat:@"Activate \"%@\"?\nInstagram must be restarted.", name]
                                                           preferredStyle:UIAlertControllerStyleAlert];
    [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
    [alert addAction:[UIAlertAction actionWithTitle:@"Activate" style:UIAlertActionStyleDefault handler:^(UIAlertAction *a) {
        NSMutableDictionary *config = [self.config mutableCopy];
        NSMutableDictionary *ac = [config[kDefaultApp] mutableCopy];
        ac[@"active"] = uuid;
        config[kDefaultApp] = ac;
        self.config = config;
        [self saveConfig:config];
        [self.tableView reloadData];
    }]];
    [self presentViewController:alert animated:YES completion:nil];
}

@end
