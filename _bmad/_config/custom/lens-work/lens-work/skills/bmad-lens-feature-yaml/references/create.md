# Create Feature YAML

Initialize a new feature.yaml from the template at `./assets/feature-template.yaml`.

## Outcome

A valid feature.yaml is created at `{governance-repo}/features/{domain}/{service}/{featureId}/feature.yaml` with all identity fields populated and lifecycle set to `preplan`.

## Process

Run the create operation:

```bash
python3 ./scripts/feature-yaml-ops.py create \
  --governance-repo {governance_repo} \
  --feature-id {featureId} \
  --domain {domain} \
  --service {service} \
  --name "{feature name}" \
  --description "{description}" \
  --track {track} \
  --username {username}
```

The script creates the directory structure, copies the template, and populates fields. If any required fields are missing, prompt the user for them.

After creation, confirm the feature.yaml location and contents to the user.
