#include <Geode/Geode.hpp>
#include <Geode/modify/MenuLayer.hpp>
#include <cstdio>
using namespace geode::prelude;

class $modify(WardenProofConsumer, MenuLayer) {
    static void onModify(auto& self) {
        auto result = self.setHookPriorityPost("MenuLayer::init", 200);
        log::info("PROOF consumer priority configured: {}", result.isOk());
    }

    bool init() {
        if (!MenuLayer::init()) {
            log::error("PROOF consumer base initialization failed");
            return false;
        }
        auto node = this->getChildByID("bottom-menu");
        std::fprintf(stderr, "WARDEN_PROOF consumer before access node=%s\n", node ? "present" : "absent");
        std::fflush(stderr);
        log::info("PROOF consumer before access node present: {}", node != nullptr);
        if (!node) {
            log::info("PROOF consumer optional label skipped; initialization succeeds");
            return true;
        }
        auto label = CCLabelBMFont::create("WARDEN PROOF", "bigFont.fnt");
        label->setScale(0.25f);
        label->setID("proof-label"_spr);
        node->addChild(label);
        label->setPosition(node->getContentSize() / 2);
        log::info("PROOF consumer optional label added");
        return true;
    }
};
