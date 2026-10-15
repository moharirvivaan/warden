#include <Geode/Geode.hpp>
#include <Geode/modify/MenuLayer.hpp>
#include <cstdio>
using namespace geode::prelude;

class $modify(WardenProofRemover, MenuLayer) {
    static void onModify(auto& self) {
        auto result = self.setHookPriorityPost("MenuLayer::init", 100);
        log::info("PROOF remover priority configured: {}", result.isOk());
    }

    bool init() {
        if (!MenuLayer::init()) {
            log::error("PROOF remover base initialization failed");
            return false;
        }
        auto node = this->getChildByID("bottom-menu");
        std::fprintf(stderr, "WARDEN_PROOF remover before removal node=%s\n", node ? "present" : "absent");
        std::fflush(stderr);
        log::info("PROOF remover before removal node present: {}", node != nullptr);
        if (node) {
            node->removeFromParent();
        }
        log::info("PROOF remover completed; bottom-menu present: {}",
                  this->getChildByID("bottom-menu") != nullptr);
        return true;
    }
};
