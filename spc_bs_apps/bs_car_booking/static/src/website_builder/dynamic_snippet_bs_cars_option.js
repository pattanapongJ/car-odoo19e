import { BaseOptionComponent } from "@html_builder/core/utils";
import { useDynamicSnippetOption } from "@website/builder/plugins/options/dynamic_snippet_hook";

// Reuses the base DynamicSnippetOption template (filter / template / record
// count rows) — we only need the model-specific defaults, no extra controls.
export class DynamicSnippetBsCarsOption extends BaseOptionComponent {
    static template = "website.DynamicSnippetOption";
    static dependencies = ["dynamicSnippetBsCarsOption"];
    static selector = ".s_bs_cars_snippet";
    setup() {
        super.setup();
        const { getModelNameFilter } = this.dependencies.dynamicSnippetBsCarsOption;
        this.dynamicOptionParams = useDynamicSnippetOption(getModelNameFilter());
    }
}
