#import "ScalePrefsRootListController.h"
#import "ScalePrefsContainerListController.h"

@implementation ScalePrefsRootListController

- (NSArray *)specifiers {
    if (!_specifiers) {
        _specifiers = [self loadSpecifiersFromPlistName:@"Root" target:self];
    }
    return _specifiers;
}

- (void)openContainers {
    ScalePrefsContainerListController *vc = [[ScalePrefsContainerListController alloc] initWithStyle:UITableViewStyleGrouped];
    [self.navigationController pushViewController:vc animated:YES];
}

@end
