"""Observed hook source facts using the real selected SDK, not runtime proof."""
import unittest
import test_analyzer
PREFIX = test_analyzer.PREFIX


class HookBehaviorTests(unittest.TestCase):
    fixture = test_analyzer.AnalyzerTests.fixture
    scan = test_analyzer.AnalyzerTests.scan
    run_warden = test_analyzer.AnalyzerTests.run_warden


def _body(report):
    return report['hooks'][0]['behavior']


def test_direct_and_nested(self):
    result, report = self.scan({'main.cpp': PREFIX + '''
struct $modify(Behavior, MenuLayer) {
 bool init() {
   if (!MenuLayer::init()) return false;
   auto f = [this] { MenuLayer::init(); };
   return true;
 }
};
'''})
    self.assertEqual(result.returncode, 0, result.stdout)
    self.assertEqual([c['context'] for c in _body(report)['forwarding_calls']], ['condition', 'nested_callable'])
    self.assertEqual(_body(report)['scope'], 'source_facts_only')


def test_other_receiver_and_overload(self):
    result, report = self.scan({'main.cpp': PREFIX + '''
struct $modify(Behavior, MenuLayer) {
 bool init() { auto other = MenuLayer::create(); other->init(); return true; }
 bool init(int) { return MenuLayer::init(); }
};
'''})
    self.assertEqual(result.returncode, 0, result.stdout)
    self.assertEqual(_body(report)['forwarding_calls'], [])
    self.assertTrue(_body(report)['unknown'])


def test_priority_request(self):
    result, report = self.scan({'main.cpp': PREFIX + '''
struct $modify(Behavior, MenuLayer) {
 static void onModify(auto& self) {
   if (!self.setHookPriority("MenuLayer::init", 2000)) {}
 }
 bool init() { return MenuLayer::init(); }
};
'''})
    self.assertIn(result.returncode, (0, 1), result.stdout)
    requests = _body(report)['priority_requests']
    self.assertEqual(len(requests), 1)
    self.assertEqual(requests[0]['status'], 'observed_constant')
    self.assertEqual(requests[0]['pre_order_value'], 2000)


def test_out_of_line(self):
    result, report = self.scan({'main.cpp': PREFIX + '''
struct $modify(Behavior, MenuLayer) { bool init(); };
bool Behavior::init() { return MenuLayer::init(); }
'''})
    self.assertEqual(result.returncode, 0, result.stdout)
    self.assertEqual(len(_body(report)['forwarding_calls']), 1)


def test_header_disagreement(self):
    result, report = self.scan({
        'shared.hpp': '#pragma once\n' + PREFIX + '''
struct $modify(Behavior, MenuLayer) { bool init() {
#if FORWARD
 return MenuLayer::init();
#else
 return true;
#endif
} };
''',
        'one.cpp': '#define FORWARD 1\n#include "shared.hpp"\n',
        'two.cpp': '#define FORWARD 0\n#include "shared.hpp"\n'})
    self.assertEqual(len(report['hooks']), 1)
    self.assertTrue(any('translation' in u['reason'] for u in _body(report)['unknown']))


for _test in [test_direct_and_nested, test_other_receiver_and_overload, test_priority_request,
              test_out_of_line, test_header_disagreement]:
    setattr(HookBehaviorTests, _test.__name__, _test)

def test_nested_priority_condition_is_not_unconditional(self):
    result, report = self.scan({'main.cpp': PREFIX + '''
struct $modify(Behavior, MenuLayer) {
 static void onModify(auto& self) {
   if (Mod::get()->getSettingValue<bool>("enabled")) {
     if (!self.setHookPriority("MenuLayer::init", 2000)) {}
   }
 }
 bool init() { return MenuLayer::init(); }
};
'''})
    self.assertEqual(_body(report)['priority_requests'][0]['status'], 'unknown')


def test_post_priority_and_int_min(self):
    for number, expected in [('-1000', 1000), ('(-2147483647-1)', None)]:
        result, report = self.scan({'main.cpp': PREFIX + '''
struct $modify(Behavior, MenuLayer) {
 static void onModify(auto& self) { (void)self.setHookPriorityPost("MenuLayer::init", NUMBER); }
 bool init() { return MenuLayer::init(); }
};
'''.replace('NUMBER', number)})
        self.assertEqual(_body(report)['priority_requests'][0]['pre_order_value'], expected)

HookBehaviorTests.test_nested_priority_condition_is_not_unconditional = test_nested_priority_condition_is_not_unconditional
HookBehaviorTests.test_post_priority_and_int_min = test_post_priority_and_int_min

def test_dynamic_relative_and_conditional_requests(self):
    cases = [
        ('(void)self.setHookPriority("MenuLayer::init", Mod::get()->getSettingValue<int>("priority"));', 'unknown'),
        ('(void)self.setHookPriorityAfter("MenuLayer::init", "peer.mod");', 'observed_relative'),
        ('if (Mod::get()->getSettingValue<bool>("enabled")) (void)self.setHookPriority("MenuLayer::init", 10);', 'unknown'),
    ]
    for body, status in cases:
        result, report = self.scan({'main.cpp': PREFIX + '''
struct $modify(Behavior, MenuLayer) {
 static void onModify(auto& self) { BODY }
 bool init() { return MenuLayer::init(); }
};
'''.replace('BODY', body)})
        self.assertIn(result.returncode, (0, 1), result.stdout)
        self.assertEqual(_body(report)['priority_requests'][0]['status'], status)


def test_priority_lookalike_and_inactive_calls(self):
    result, report = self.scan({'main.cpp': PREFIX + '''
struct Fake { int setHookPriority(const char*, int) { return 0; } };
struct $modify(Behavior, MenuLayer) {
 static void onModify(auto& self) { Fake other; other.setHookPriority("MenuLayer::init", 77); }
 bool init() {
#if 0
   MenuLayer::init();
#endif
   // MenuLayer::init();
   return true;
 }
};
'''})
    self.assertEqual(_body(report)['priority_requests'], [])
    self.assertEqual(_body(report)['forwarding_calls'], [])

HookBehaviorTests.test_dynamic_relative_and_conditional_requests = test_dynamic_relative_and_conditional_requests
HookBehaviorTests.test_priority_lookalike_and_inactive_calls = test_priority_lookalike_and_inactive_calls

def test_registered_overload_priority_name_is_ambiguous(self):
    source = '#include <Geode/Geode.hpp>\n#include <Geode/modify/CCNode.hpp>\nusing namespace geode::prelude;\n' + '''
struct $modify(Behavior, CCNode) {
 static void onModify(auto& self) { (void)self.setHookPriority("cocos2d::CCNode::setPosition", 10); }
 void setPosition(CCPoint const& p) { CCNode::setPosition(p); }
 void setPosition(float x, float y) { CCNode::setPosition(x, y); }
};
'''
    result, report = self.scan({'main.cpp': source})
    self.assertEqual(len(report['hooks']), 2, result.stdout)
    for hook in report['hooks']:
        self.assertEqual(hook['behavior']['priority_requests'][0]['status'], 'unknown')
        self.assertTrue(any('overload' in u['reason'] for u in hook['behavior']['unknown']))

HookBehaviorTests.test_registered_overload_priority_name_is_ambiguous = test_registered_overload_priority_name_is_ambiguous
