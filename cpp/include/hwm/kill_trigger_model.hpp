#pragma once
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>
namespace hwm {
struct KillTriggerRule {
    uint32_t ability_id=0;
    std::string code;
    double probability=0.0;
    int increment=1;
    bool enabled=false;
};
class KillTriggerModel {
public:
    KillTriggerModel();
    explicit KillTriggerModel(const std::string& path);
    bool load(const std::string& path);
    [[nodiscard]] bool loaded() const { return loaded_; }
    [[nodiscard]] const KillTriggerRule* rule(std::string_view code) const;
private:
    std::vector<KillTriggerRule> rules_;
    bool loaded_=false;
};
}
