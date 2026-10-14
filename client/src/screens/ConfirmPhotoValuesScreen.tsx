import { useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import {
  buildConfirmedReading,
  buildFields,
  canConfirm,
  fieldError,
  SERVING_PATH,
  type ConfirmedReading,
  type Field,
  type LabelReading,
} from '../photoConfirmation';

type Props = {
  reading: LabelReading;
  onConfirm: (result: ConfirmedReading) => void;
  onRetake: () => void;
};

export const NO_TABLE_MESSAGE =
  "We couldn't find a Nutrition Facts table in this photo. Try a clearer photo of the table.";

/**
 * Shows each value read from a Nutrition Facts photo and lets the user confirm or correct
 * it before it is used (#39, Q1). Values the user does not confirm are not used for
 * explanations (#37) or whole-package totals (#36).
 */
export default function ConfirmPhotoValuesScreen({ reading, onConfirm, onRetake }: Props) {
  if (reading.status === 'not_found') {
    return (
      <View style={styles.container}>
        <Text style={styles.heading}>No Nutrition Facts table found</Text>
        <Text style={styles.help}>{NO_TABLE_MESSAGE}</Text>
        <Pressable style={[styles.button, styles.buttonPrimary]} onPress={onRetake}>
          <Text style={styles.buttonPrimaryText}>Retake photo</Text>
        </Pressable>
      </View>
    );
  }
  return <ConfirmForm reading={reading} onConfirm={onConfirm} onRetake={onRetake} />;
}

function ConfirmForm({
  reading,
  onConfirm,
  onRetake,
}: Props & { reading: Extract<LabelReading, { status: 'found' }> }) {
  const [fields, setFields] = useState<Field[]>(() => buildFields(reading));

  const update = (path: string, change: Partial<Field>) =>
    setFields((current) =>
      current.map((field) =>
        field.path === path
          ? // Any edit needs a fresh confirmation, so a changed value is never pre-confirmed.
            { ...field, ...change, confirmed: change.confirmed ?? false }
          : field,
      ),
    );

  const confirmable = fields.filter(canConfirm);
  const allConfirmed = confirmable.length > 0 && confirmable.every((f) => f.confirmed);
  const highlighted = fields.filter((f) => f.highlighted);
  const nutrients = fields.filter((f) => !f.highlighted);

  return (
    <View style={styles.container}>
      <Text style={styles.heading}>Check the values from your photo</Text>
      <Text style={styles.help}>
        These were read from the photo automatically and may contain mistakes. Compare each
        one with the label, fix anything that is wrong, and confirm it. Values you don't
        confirm are not used.
      </Text>

      <View style={styles.highlightBox}>
        <Text style={styles.highlightTitle}>Check these first</Text>
        <Text style={styles.help}>The serving size and servings per package change every total.</Text>
        {highlighted.map((field) => (
          <FieldRow key={field.path} field={field} update={update} />
        ))}
      </View>

      {nutrients.map((field) => (
        <FieldRow key={field.path} field={field} update={update} />
      ))}

      <Pressable
        style={[styles.button, styles.buttonSecondary]}
        onPress={() => setFields((current) => current.map((f) => ({ ...f, confirmed: canConfirm(f) })))}
      >
        <Text style={styles.buttonSecondaryText}>
          {allConfirmed ? 'All values confirmed' : 'Confirm all values I checked'}
        </Text>
      </Pressable>
      <View style={styles.buttons}>
        <Pressable style={[styles.button, styles.buttonSecondary, styles.flex]} onPress={onRetake}>
          <Text style={styles.buttonSecondaryText}>Retake photo</Text>
        </Pressable>
        <Pressable
          style={[styles.button, styles.buttonPrimary, styles.flex]}
          onPress={() => onConfirm(buildConfirmedReading(fields))}
        >
          <Text style={styles.buttonPrimaryText}>Use these values</Text>
        </Pressable>
      </View>
    </View>
  );
}

function FieldRow({
  field,
  update,
}: {
  field: Field;
  update: (path: string, change: Partial<Field>) => void;
}) {
  const error = fieldError(field);
  const confirmable = canConfirm(field);
  return (
    <View style={[styles.row, field.confirmed && styles.rowConfirmed]}>
      <View style={styles.rowHeader}>
        <Text style={styles.label}>{field.label}</Text>
        <Pressable
          accessibilityRole="checkbox"
          accessibilityState={{ checked: field.confirmed, disabled: !confirmable }}
          disabled={!confirmable}
          onPress={() => update(field.path, { confirmed: !field.confirmed })}
          style={[styles.check, field.confirmed && styles.checkOn, !confirmable && styles.dim]}
        >
          <Text style={field.confirmed ? styles.checkTextOn : styles.checkText}>
            {field.confirmed ? '✓ Confirmed by you' : 'Confirm'}
          </Text>
        </Pressable>
      </View>
      {field.unreadable ? (
        <Text style={styles.warning}>Couldn't read this clearly. Enter it from the label, or leave it blank.</Text>
      ) : null}
      <View style={styles.inputs}>
        <TextInput
          style={styles.input}
          value={field.amountText}
          onChangeText={(text) => update(field.path, { amountText: text })}
          keyboardType="decimal-pad"
          placeholder="Not read"
          accessibilityLabel={`${field.label} amount`}
        />
        {field.path === SERVING_PATH ? (
          <View style={styles.units}>
            {(['g', 'ml'] as const).map((unit) => (
              <Pressable
                key={unit}
                onPress={() => update(field.path, { unit })}
                style={[styles.unit, field.unit === unit && styles.unitOn]}
              >
                <Text style={field.unit === unit ? styles.checkTextOn : styles.checkText}>
                  {unit === 'ml' ? 'mL' : unit}
                </Text>
              </Pressable>
            ))}
          </View>
        ) : field.unit ? (
          <Text style={styles.unitText}>{field.unit}</Text>
        ) : null}
        {field.dvText !== null ? (
          <>
            <TextInput
              style={[styles.input, styles.dvInput]}
              value={field.dvText}
              onChangeText={(text) => update(field.path, { dvText: text })}
              keyboardType="decimal-pad"
              placeholder="—"
              accessibilityLabel={`${field.label} percent daily value`}
            />
            <Text style={styles.unitText}>% DV</Text>
          </>
        ) : null}
      </View>
      {error ? <Text style={styles.error}>{error}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignSelf: 'stretch', gap: 12 },
  heading: { fontSize: 18, fontWeight: '600', color: '#1a1a1a' },
  help: { color: '#555', lineHeight: 20 },
  highlightBox: {
    gap: 8,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e0b252',
    backgroundColor: '#fff6e5',
  },
  highlightTitle: { fontWeight: '600', color: '#7a4b00' },
  row: {
    gap: 6,
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: '#e2e5e2',
    backgroundColor: '#fff',
  },
  rowConfirmed: { borderColor: '#1b7f3b', backgroundColor: '#f1faf3' },
  rowHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', gap: 8 },
  label: { fontWeight: '600', color: '#1a1a1a', flexShrink: 1 },
  inputs: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  input: {
    minWidth: 90,
    borderWidth: 1,
    borderColor: '#c9cfc9',
    borderRadius: 6,
    paddingVertical: 8,
    paddingHorizontal: 10,
    fontSize: 16,
    color: '#1a1a1a',
    backgroundColor: '#fff',
  },
  dvInput: { minWidth: 60 },
  unitText: { color: '#555' },
  units: { flexDirection: 'row', gap: 6 },
  unit: { borderWidth: 1, borderColor: '#1b7f3b', borderRadius: 6, paddingVertical: 6, paddingHorizontal: 10 },
  unitOn: { backgroundColor: '#1b7f3b' },
  check: { borderWidth: 1, borderColor: '#1b7f3b', borderRadius: 16, paddingVertical: 4, paddingHorizontal: 10 },
  checkOn: { backgroundColor: '#1b7f3b' },
  checkText: { color: '#1b7f3b', fontWeight: '600' },
  checkTextOn: { color: '#fff', fontWeight: '600' },
  dim: { opacity: 0.4 },
  warning: { color: '#7a4b00' },
  error: { color: '#b3261e' },
  buttons: { flexDirection: 'row', gap: 12 },
  flex: { flex: 1 },
  button: { paddingVertical: 12, paddingHorizontal: 12, borderRadius: 8, borderWidth: 1, alignItems: 'center' },
  buttonPrimary: { backgroundColor: '#1b7f3b', borderColor: '#1b7f3b' },
  buttonSecondary: { backgroundColor: '#fff', borderColor: '#1b7f3b' },
  buttonPrimaryText: { color: '#fff', fontWeight: '600' },
  buttonSecondaryText: { color: '#1b7f3b', fontWeight: '600' },
});
