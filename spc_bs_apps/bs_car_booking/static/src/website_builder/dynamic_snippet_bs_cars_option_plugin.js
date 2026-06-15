import {
    DYNAMIC_SNIPPET,
    setDatasetIfUndefined,
} from "@website/builder/plugins/options/dynamic_snippet_option_plugin";
import { Plugin } from "@html_editor/plugin";
import { withSequence } from "@html_editor/utils/resource";
import { registry } from "@web/core/registry";
import { DynamicSnippetBsCarsOption } from "./dynamic_snippet_bs_cars_option";

// Makes the s_bs_cars dynamic block turnkey: on drop it auto-selects the
// bs.car.model "Cars" filter (+ the card template, via the s_bs_car_model_card
// class on the section) and a sensible record count, so it syncs live data
// without the user having to pick a filter manually.
class DynamicSnippetBsCarsOptionPlugin extends Plugin {
    static id = "dynamicSnippetBsCarsOption";
    static dependencies = ["dynamicSnippetOption"];
    static shared = ["getModelNameFilter"];
    modelNameFilter = "bs.car.model";
    resources = {
        builder_options: withSequence(DYNAMIC_SNIPPET, DynamicSnippetBsCarsOption),
        on_snippet_dropped_handlers: this.onSnippetDropped.bind(this),
    };
    getModelNameFilter() {
        return this.modelNameFilter;
    }
    async onSnippetDropped({ snippetEl }) {
        if (snippetEl.matches(DynamicSnippetBsCarsOption.selector)) {
            setDatasetIfUndefined(snippetEl, "numberOfRecords", 3);
            await this.dependencies.dynamicSnippetOption.setOptionsDefaultValues(
                snippetEl,
                this.modelNameFilter
            );
        }
    }
}

registry
    .category("website-plugins")
    .add(DynamicSnippetBsCarsOptionPlugin.id, DynamicSnippetBsCarsOptionPlugin);
